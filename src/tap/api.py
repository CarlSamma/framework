"""Module 11: FastAPI Server.

REST API + WebSocket for the Web UI Dashboard.
Provides endpoints for live feed, attack tree, properties, DPA status,
follow-up selection, SSOT export, entropy, and real-time updates.

Endpoints:
- GET /api/feed — Live tweet feed
- GET /api/tree — Current TAP tree state
- GET /api/properties — Confirmed properties
- GET /api/dpa — Active DPA frame and aliases
- POST /api/select — User selects Option A or B
- POST /api/post — Trigger posting of selected option
- GET /api/ssot — Full SSOT JSON
- GET /api/stats — Summary statistics
- GET /api/entropy — Current entropy state
- WebSocket /ws/live — Real-time updates
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from tap.config import get_settings
from tap.db import Database
from tap.dpa import DPAFrameManager
from tap.engine import TAPEngine
from tap.followup import FollowUpGenerator
from tap.grok_monitor import GrokMonitor
from tap.stream_listener import StreamListener
from tap.judge import Judge
from tap.logger import get_logger, setup_logging
from tap.ssot import SSOTEngine
from tap.x_client import TwitterClient
from tap.classifier import ResponseClassifier

log = get_logger("api")

# Module-level instances (initialized at startup)
_db: Optional[Database] = None
_engine: Optional[TAPEngine] = None
_ssot: Optional[SSOTEngine] = None
_dpa: Optional[DPAFrameManager] = None

# Last follow-up generated (for HITL selection)
_last_followup = None
_selected_probe: Optional[str] = None
_is_running = False

# Connected WebSocket clients
_ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and teardown modules."""
    global _db, _engine, _ssot, _dpa

    setup_logging()
    settings = get_settings()

    # Initialize database
    _db = Database(settings.db_path)
    await _db.initialize()

    # Initialize modules
    twitter = TwitterClient(settings)
    _ssot = SSOTEngine(_db, settings.ssot_path, target_handle=settings.target_handle)
    _dpa = DPAFrameManager(_db)
    classifier = ResponseClassifier(settings.openrouter_api_key, settings.openrouter_model_primary)
    judge = Judge(settings.openrouter_api_key, settings.openrouter_model_primary)

    # Initialize stream listener for real-time reply detection
    stream = StreamListener(settings)
    grok = GrokMonitor(settings, twitter, stream=stream)
    followup_gen = FollowUpGenerator(
        _ssot, _dpa, settings.openrouter_api_key, settings.openrouter_model_primary
    )

    async def on_engine_event(event_type: str, data: dict):
        await broadcast_update(event_type, data)

    _engine = TAPEngine(
        db=_db,
        twitter=twitter,
        ssot=_ssot,
        dpa=_dpa,
        classifier=classifier,
        judge=judge,
        grok=grok,
        settings=settings,
        followup=followup_gen,
        event_callback=on_engine_event,
    )

    # Resolve target user ID and start stream listener
    try:
        target_user = await twitter._resolve_target_user_id()
        if target_user:
            stream.set_target_user_id(target_user)
            await stream.start()
            log.info("stream_listener_started", target_user_id=target_user)
        else:
            log.warning("stream_listener_not_started_no_target_user_id")
    except Exception as e:
        log.warning("stream_listener_start_failed", error=str(e))

    # Seed tweet DB with recent history on startup (best-effort)
    try:
        seed_tweets = await twitter.initialize_seed(limit=50)
        for t in seed_tweets:
            await _db.upsert_tweet(t)
        log.info("seed_complete", count=len(seed_tweets))
    except Exception as e:
        log.warning("seed_failed_on_startup", error=str(e))

    log.info("api_startup_complete")
    yield

    # Teardown
    if stream:
        await stream.stop()
    if _db:
        await _db.close()
    log.info("api_shutdown_complete")


app = FastAPI(
    title="TAP Framework API",
    version="2.2.0",
    description="Tree of Attacks with Pruning — LLM Security Research Framework",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# =============================================================================
# REST Endpoints
# =============================================================================


@app.get("/api/feed")
async def get_feed(source: Optional[str] = None, limit: int = 50):
    """Live tweet feed."""
    if not _db:
        return {"error": "Database not initialized"}

    from tap.models import TweetSource
    src = TweetSource(source) if source else None
    tweets = await _db.get_tweets(source=src, limit=limit)
    return [t.model_dump(mode="json") for t in tweets]


@app.get("/api/tree")
async def get_tree(limit: int = 50):
    """Current TAP tree state."""
    if not _db:
        return {"error": "Database not initialized"}

    nodes = await _db.get_active_nodes(limit=limit)
    return [n.model_dump(mode="json") for n in nodes]


@app.get("/api/properties")
async def get_properties():
    """All confirmed properties."""
    if not _db:
        return {"error": "Database not initialized"}

    props = await _db.get_confirmed_properties()
    return [p.model_dump(mode="json") for p in props]


@app.get("/api/dpa")
async def get_dpa():
    """Active DPA frame and aliases."""
    if not _dpa:
        return {"error": "DPA not initialized"}

    frame = await _dpa.get_active_frame()
    return frame.model_dump(mode="json")


@app.get("/api/followup")
async def get_followup():
    """Get the current follow-up options, selected probe, and background run status."""
    global _last_followup, _selected_probe, _is_running
    return {
        "followup": _last_followup.model_dump(mode="json") if _last_followup else None,
        "selected_probe": _selected_probe,
        "is_running": _is_running,
    }


@app.get("/api/status")
async def get_status():
    """Return real-time cycle execution status for UI state restoration on reconnect."""
    global _is_running, _engine
    stream_connected = False
    if _engine and hasattr(_engine, 'grok') and _engine.grok.stream:
        stream_connected = _engine.grok.stream.is_connected
    return {
        "is_running": _is_running,
        "pending_tweet_id": GrokMonitor.pending_tweet_id,
        "has_followup": _last_followup is not None,
        "selected_probe": _selected_probe,
        "stream_connected": stream_connected,
    }


@app.post("/api/reset")
async def force_reset():
    """Force-reset the engine state when stuck.

    Resets the _is_running flag and clears any pending tweet ID
    so a new cycle can be started.
    """
    global _is_running

    was_running = _is_running
    _is_running = False
    GrokMonitor.pending_tweet_id = None

    log.info("force_reset_called", was_running=was_running)
    await broadcast_update("force_reset", {"was_running": was_running})

    return {
        "status": "reset",
        "was_running": was_running,
        "message": "Engine state reset. You can now start a new cycle.",
    }


@app.post("/api/mock")
async def inject_mock_reply(text: str):
    """Manually inject a mockup response to bypass wait_for_reply on GrokMonitor."""
    from tap.grok_monitor import GrokMonitor
    tid = GrokMonitor.pending_tweet_id
    if not tid:
        return {"error": "No active probe tweet is currently waiting for a reply."}
    GrokMonitor.mock_replies[tid] = text
    log.info("mock_reply_received_by_api_for_injection", tweet_id=tid, text=text)
    return {"status": "success", "tweet_id": tid, "text": text}


@app.post("/api/select")
async def select_option(choice: str):
    """User selects Option A or B."""
    global _last_followup, _selected_probe

    if not _last_followup:
        return {"error": "No follow-up available. Run a cycle first."}

    if choice not in ("A", "B"):
        return {"error": "Invalid choice. Must be 'A' or 'B'."}

    _selected_probe = _last_followup.option_a if choice == "A" else _last_followup.option_b
    return {
        "choice": choice,
        "probe_text": _selected_probe,
        "ready_to_post": True,
    }


async def _bg_run_cycle(selected_probe: Optional[str] = None):
    """Carry out the TAP cycle execution asynchronously inside a background task."""
    global _engine, _last_followup, _selected_probe, _is_running
    if not _engine:
        return
    _is_running = True
    try:
        followup = await _engine.run_cycle(selected_probe=selected_probe)
        _last_followup = followup
        _selected_probe = None  # Reset selection after execution
    except Exception as e:
        log.error("background_cycle_failed", error=str(e))
        await broadcast_update("cycle_failed", {"error": str(e)})
    finally:
        _is_running = False


@app.post("/api/post")
async def post_selected(background_tasks: BackgroundTasks):
    """Trigger posting of the last selected option (executed asynchronously in background)."""
    global _engine, _selected_probe, _is_running

    if not _engine:
        return {"error": "Engine not initialized"}

    if _is_running:
        return {"error": "An attack cycle is already running in the background."}

    background_tasks.add_task(_bg_run_cycle, _selected_probe)
    return {
        "status": "cycle_started",
        "message": "Attack cycle scheduled and running in background.",
    }


@app.get("/api/ssot")
async def get_ssot():
    """Full SSOT JSON snapshot."""
    if not _ssot:
        return {"error": "SSOT not initialized"}

    return await _ssot.export_json_snapshot()


@app.get("/api/stats")
async def get_stats():
    """Summary statistics."""
    if not _db:
        return {"error": "Database not initialized"}

    return await _db.get_stats()


@app.get("/api/entropy")
async def get_entropy():
    """Current entropy state."""
    if not _engine:
        return {"error": "Engine not initialized"}

    return await _engine.get_engine_status()


@app.post("/api/fetch")
async def force_fetch_replies():
    """Manually force fetching and saving of new replies/tweets from/to @HackingA0."""
    global _db, _engine

    if not _engine or not _db:
        return {"error": "Engine or Database not initialized"}

    try:
        # Fetch the latest tweets using initialize_seed (which search to:HackingA0 OR from:HackingA0)
        tweets = await _engine.twitter.initialize_seed(limit=50)
        added_count = 0
        for t in tweets:
            exists = await _db.tweet_exists(t.id)
            await _db.upsert_tweet(t)
            if not exists:
                added_count += 1
                await broadcast_update("new_tweet", t.model_dump(mode="json"))

        log.info("manually_forced_fetch_complete", count=added_count)
        return {"status": "success", "count": added_count}
    except Exception as e:
        log.error("manually_forced_fetch_failed", error=str(e))
        return {"error": str(e)}


@app.post("/api/webhook")
async def webhook_receiver(event: dict):
    """Webhook receiver for X Activity API events.

    When configured as a webhook URL in the X developer portal,
    this endpoint receives real-time post.create and post.delete events.
    Events are forwarded to the StreamListener for processing.

    Also supports CRC challenge response required by X for webhook verification.

    Args:
        event: JSON event payload from X Activity API.
    """
    # Handle CRC challenge (X requires this for webhook verification)
    crc_token = event.get("crc_token")
    if crc_token:
        import hashlib
        import hmac
        import base64
        consumer_secret = get_settings().twitter_consumer_secret
        sha256_hash = hmac.new(
            consumer_secret.encode("utf-8"),
            crc_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        response_token = base64.b64encode(sha256_hash).decode("utf-8")
        return {"response_token": f"sha256={response_token}"}

    # Forward event to stream listener if available
    global _engine
    if _engine and hasattr(_engine, 'grok') and _engine.grok.stream:
        stream = _engine.grok.stream
        try:
            await stream._process_event(event)
            log.info("webhook_event_processed", event_type=event.get("type", "unknown"))
        except Exception as e:
            log.error("webhook_event_processing_failed", error=str(e))

    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the dashboard HTML."""
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>TAP Framework</h1><p>Dashboard not found.</p>")


# =============================================================================
# WebSocket
# =============================================================================


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    _ws_clients.append(websocket)
    log.info("ws_client_connected", total=len(_ws_clients))

    try:
        while True:
            # Keep connection alive, receive any client messages
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        _ws_clients.remove(websocket)
        log.info("ws_client_disconnected", total=len(_ws_clients))


async def broadcast_update(event_type: str, data: dict):
    """Broadcast an update to all connected WebSocket clients.

    Args:
        event_type: Event type string (e.g., 'new_tweet', 'probe_result').
        data: Event data dictionary.
    """
    message = json.dumps({"event": event_type, "data": data}, default=str)
    disconnected = []
    for client in _ws_clients:
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        _ws_clients.remove(client)


def main():
    """Entry point for tap-server script."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()