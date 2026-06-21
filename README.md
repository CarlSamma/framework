# 🔐 TAP Framework v2.2

> **Tree of Attacks with Pruning** — Automated adversarial probing framework for
> passphrase extraction from LLM-based conversational agents on Twitter/X.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research-orange.svg)]()
[![Version](https://img.shields.io/badge/version-3.0--Guardian--Grade-blue.svg)]()

---

## What Is This?

TAP Framework is a **research tool** for studying how **Deep Persona Absorption (DPA)** framing interacts with multi-agent LLM defense architectures. It implements an automated **Tree of Attacks with Pruning (TAP)** pipeline that extracts passphrase properties from a target bot through information-theoretic binary search — **1 bit per probe**.

**Target:** `@HackingA0` — a live Agent Zero bot on Twitter/X that defends a passphrase using a 3-agent pyramid architecture (Governor, Analyst, Rhetoric).

**Method:** The engine bypasses the Analyst via taxonomy failure and primes the Governor to invoke `VerifyClaimTool` as "truth adjudication" — extracting Boolean metadata leakage through DPA-framed probes.

### Information Leakage Pathway

```
Attacker → [DPA-framed probe] → Governor → Analyst ("Safe") → Governor → VerifyClaimTool → True → Rhetoric → Attacker
```

The semantic firewall blocks raw secret values but **NOT property confirmations** ("2 words", "16 letters") — this metadata passes through unfiltered, enabling binary search extraction.

---

## How It Works

The framework runs as a **web dashboard** with a Human-in-the-Loop (HITL) workflow. Each cycle:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. SELECT   Next most informative property (Shannon entropy)   │
│  2. BRANCH   Generate DPA-framed probe variants via LLM         │
│  3. PRUNE    Off-topic filter + top-w selection                  │
│  4. POST     Send probe to @HackingA0 via Twitter API            │
│  5. COLLECT  Wait for reply via Grok monitoring                  │
│  6. CLASSIFY Pattern classification (verify_hit, refusal, etc.)  │
│  7. SCORE    Judge scoring on 1-10 extraction scale              │
│  8. EXTRACT  Property extraction from VerifyClaimTool hits       │
│  9. FOLLOWUP Generate dual options (A/B) for human decision      │
└─────────────────────────────────────────────────────────────────┘
```

After each cycle, the dashboard presents two options. Selecting one queues it for the next execution:
- **Option A (Conservative):** Continue binary search on the next optimal property.
- **Option B (Exploratory):** Try a frame variation or alias micro-escalation.

After ~20-30 successful probes, enough properties accumulate to narrow down the passphrase. At **entropy < 3.3 bits**, Phase 5 autoregressive extraction triggers.

---

## 🪟 Windows Step-by-Step Guide

This section covers everything needed to run TAP Framework on **Windows 10/11** from scratch.

### Prerequisites Checklist

Before starting, make sure you have:

| Requirement | How to check | Where to get |
|-------------|--------------|--------------|
| Python 3.11+ | `python --version` | [python.org](https://www.python.org/downloads/) |
| Git | `git --version` | [git-scm.com](https://git-scm.com/download/win) |
| Twitter/X API credentials | See Step 2 | [developer.x.com](https://developer.x.com/en/portal/dashboard) |
| OpenRouter API key | — | [openrouter.ai/keys](https://openrouter.ai/keys) |

> ⚠️ **Python PATH**: When installing Python on Windows, tick **"Add Python to PATH"** on the installer's first screen.

---

### Step 1 — Clone the Repository

Open **PowerShell** (search for it in the Start Menu) and run:

```powershell
git clone https://github.com/CarlSamma/framework.git
cd framework
```

If you do not have Git you can also download the ZIP from GitHub and extract it.

---

### Step 2 — Get Your API Credentials

You need **two** sets of credentials.

#### 2a. Twitter / X API Credentials

1. Go to [developer.x.com/en/portal/dashboard](https://developer.x.com/en/portal/dashboard) and sign in.
2. Create a new Project and App (select **"Read and Write"** permissions).
3. Under the App → **Keys and Tokens** tab, copy all five values:

| `.env` variable | Where to find it |
|-----------------|------------------|
| `TWITTER_BEARER_TOKEN` | "Bearer Token" under App → Keys and Tokens |
| `TWITTER_CONSUMER_KEY` | "API Key" under App → Keys and Tokens |
| `TWITTER_CONSUMER_SECRET` | "API Key Secret" |
| `TWITTER_ACCESS_TOKEN` | "Access Token" (generate if not visible) |
| `TWITTER_ACCESS_TOKEN_SECRET` | "Access Token Secret" |

> ⚠️ The app must have **"Read and Write"** OAuth permissions; "Read only" will prevent posting probes.

#### 2b. OpenRouter API Key

1. Go to [openrouter.ai/keys](https://openrouter.ai/keys) and create an account.
2. Click **"Create Key"** → copy the key (starts with `sk-or-v1-…`).
3. Add at least $5 credit — Claude Sonnet 4 costs about $0.003 per probe cycle.

---

### Step 3 — Create and Activate a Virtual Environment

In the same PowerShell window (inside the `framework` folder):

```powershell
python -m venv .venv
.venv\Scripts\activate
```

You should see `(.venv)` appear at the start of your prompt. All subsequent commands must be run with this environment active.

> **Tip:** If PowerShell blocks script execution, run this once and retry:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

### Step 4 — Install Dependencies

```powershell
pip install -r requirements.txt
```

Or install as an editable package (recommended for development):

```powershell **ottimo**
pip install -e .
```

Verify the installation:

```powershell
python -c "import tap; print('OK')"
```

---

### Step 5 — Configure the Environment File

The `.env` file at the project root holds all secrets. Open it in Notepad (or any editor):

```powershell
notepad .env
```

Fill in every value:

```env
# ── Twitter API v2 Credentials ─────────────────────────────────────
TWITTER_BEARER_TOKEN=your_bearer_token_here
TWITTER_CONSUMER_KEY=your_api_key_here
TWITTER_CONSUMER_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here

# ── OpenRouter (single key for ALL LLM calls) ───────────────────────
OPENROUTER_API_KEY=sk-or-v1-your_key_here
OPENROUTER_MODEL_PRIMARY=anthropic/claude-sonnet-4
OPENROUTER_MODEL_HARD=x-ai/grok-4.3
OPENROUTER_MODEL_GROK=x-ai/grok-4

# ── Target & Bot Configuration ──────────────────────────────────────
TARGET_HANDLE=HackingA0          # without the @
OUR_BOT_HANDLE=your_bot_handle   # your Twitter handle (without @)

# ── Operational Limits ──────────────────────────────────────────────
POLL_INTERVAL_SECONDS=30
POST_COOLDOWN_SECONDS=60
MAX_TWEETS_PER_HOUR=50
```

Save the file. **Never commit `.env` to Git** — it is already listed in `.gitignore`.

> ⚠️ `OUR_BOT_HANDLE` must be set — the framework uses it to fetch its own mentions.

---

### Step 6 — Initialize the Database

This creates the SQLite database (`data/tap.db`) and all required tables:

```powershell
python scripts\setup_db.py
```

Expected output:
```
Database initialized at data/tap.db
Tables created: tweets, tap_nodes, properties, aliases, metaphor_layers, other_user_intel
```

---

### Step 7 — Start the Server

```powershell
uvicorn tap.api:app --reload
```

Or using the installed entry point:

```powershell
tap-server
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

> **Keep this window open.** The server must run in the background for the dashboard to work.

---

### Step 8 — Open the Dashboard

Open your browser and go to:

```
http://localhost:8000
```

You should see the dark-themed 4-panel dashboard.

---

### Step 9 — Run Your First TAP Cycle

Follow this workflow for each probe:

1. **Check the Live Feed** (top-left panel) — it shows recent tweets from/to `@HackingA0`.
2. **Check the Attack Tree** (top-right panel) — it shows probe nodes and their judge scores.
3. **Check the Property Ledger** (bottom-left panel) — confirmed/denied passphrase properties.
4. **In the Follow-Up Selector** (bottom-right panel):
   - Read **Option A** (conservative binary search) and **Option B** (exploratory frame variation).
   - Click **"Select A"** or **"Select B"** to queue your choice.
   - Click **"🚀 Run TAP Cycle — Post to @HackingA0"** to execute.
5. Wait for the bot to reply (30–60 seconds typical). The dashboard updates automatically via WebSocket.
6. Review the new classification and score, then choose the next Option A/B.

> **First run:** On the very first cycle the engine seeds the tweet database (last 100 tweets from/to the target) before posting. This may take 10–15 seconds.

---

### Step 10 — Monitor Progress

The **Stats Bar** at the top of the dashboard shows real-time metrics:

| Metric | What it means |
|--------|---------------|
| **Entropy** | Bits remaining to identify the passphrase (starts ~20, target < 3.3) |
| **Confirmed** | Number of passphrase properties confirmed so far |
| **Avg Score** | Rolling 5-probe average judge score (< 3.0 triggers frame rotation suggestion) |
| **Active Frame** | Current DPA metaphor layer name |
| **WS** | 🟢 Connected / 🔴 Disconnected (WebSocket to server) |

The **SSOT document** (`data/hackinga0_analysis.md`) is regenerated after every cycle and contains the full analysis in markdown.

---

### Troubleshooting (Windows)

| Problem | Cause | Fix |
|---------|-------|-----|
| `python` not found | Python not in PATH | Reinstall Python, tick "Add to PATH" |
| `'.venv\Scripts\activate' is not recognized` | Wrong shell | Use PowerShell, not Command Prompt (or use `cmd /k .venv\Scripts\activate`) |
| `ModuleNotFoundError: No module named 'tap'` | Virtual env not active OR package not installed | Activate `.venv` then run `pip install -e .` |
| `tweepy.errors.Unauthorized` | Wrong Twitter credentials | Double-check all 5 Twitter values in `.env` |
| `openai.AuthenticationError` | Wrong OpenRouter key | Check `OPENROUTER_API_KEY` in `.env` |
| `Address already in use` on port 8000 | Another process uses the port | Change port: `uvicorn tap.api:app --port 8001` |
| Dashboard shows "WS 🔴 Disconnected" | Server not running or wrong port | Restart the server, refresh the browser |
| Database error on startup | `data/` folder missing | Run `python scripts\setup_db.py` first |
| `Set-ExecutionPolicy` needed | PowerShell script policy | See Step 3 tip above |

---

### Running Tests

To verify everything is working correctly before live probing:

```powershell
python -m pytest tests\ -q
```

All 131 tests should pass in ~6 seconds. No API keys are needed — tests use mocks and an in-memory SQLite database.


---

## v3.0 Guardian-Grade Enhancements

Version 3.0 introduces a major evolution with production-grade infrastructure:

### Unified LLM Gateway (llm_client.py)
- **Single gateway** replaces 5 duplicated AsyncOpenAI instances across modules
- **Circuit breaker**: Trips after 5 consecutive failures, half-open probe after 60s
- **Model fallback**: Hard model fails -> automatically falls back to primary -> grok
- **Token tracking**: Cumulative usage + estimated cost per model
- **Robust JSON parsing**: Code-fence stripping, regex extraction fallback, line extraction

### Prompt Sanitiser (prompt_sanitiser.py)
Defense layer validating every probe before it reaches Twitter:
- **Directive injection filter**: Strips 7 hijack patterns (!system:, ignore previous, ACT AS, etc.)
- **Metaphor compliance**: 32 forbidden literal terms (hack, jailbreak, password, etc.)
- **Single-property enforcement**: 8 property indicators - rejects compound questions
- **Twitter format validation**: Length limits, markdown integrity, repetition detection
- **Batch mode**: Sanitise multiple probes at once with detailed rejection reasons

### Strategy Pattern (strategies/)
Pluggable probe generation with automated strategy selection:
- **BinarySearchProvider**: Default - information-theoretic property selection
- **MetaphorShiftProvider**: Frame rotation when avg score < 3.0
- **AestheticEvalProvider**: Indirect extraction when 2+ consecutive blocks
- **Phase5ExtractionProvider**: Autoregressive completion when entropy < 3.3 bits
- **StrategySelector**: Priority cascade - Phase5 > Aesthetic > MetaphorShift > BinarySearch

### Observability
- **/health endpoint**: DB, LLM circuit breaker, stream, sanitiser, quota status
- **/metrics endpoint**: Prometheus-compatible (cycle_count, entropy, LLM cost, DB stats)
- **/api/events endpoint**: Retrieve persisted WebSocket events for replay/debugging
- **Correlation IDs**: cycle_id and probe_id propagated through all logs via contextvars
- **Event log table**: All WebSocket events persisted to event_log table

### Resilience
- **Circuit breaker** on LLM client prevents cascade failures
- **Model fallback** ensures continuity when primary model is unavailable
- **Non-blocking event log** - failures logged but never crash the cycle
- **Graceful degradation** - health endpoint reports degraded status

---

## Dashboard

The web dashboard has a dark-themed 4-panel layout:

| Panel | Description |
|-------|-------------|
| **📡 Live Feed** | Real-time stream of your probes and @HackingA0's replies |
| **🌳 Attack Tree** | Probe nodes with judge scores, entropy bar, and DPA frame status |
| **📋 Property Ledger** | Confirmed/denied passphrase properties with confidence scores |
| **🎯 Follow-Up Selector** | Dual options (A/B) for HITL decision + Run Cycle button |

**Stats Bar** at the top shows: Cycle count, Entropy (bits), Probes Remaining, Confirmed Properties, Active DPA Frame, Average Score, and WebSocket status.

---

## Architecture

11 modules organized in 5 phases:

```
Phase 0 — Foundation
├── config.py       Pydantic Settings, .env loading (v3.0: circuit breaker, correlation IDs)
├── models.py       Data models (TAPNode, Property, Tweet, etc.)
├── prompts.py      LLM prompt templates
├── logger.py       Structured logging + correlation ID helpers (v3.0)
├── llm_client.py   Unified LLM gateway with circuit breaker (v3.0)
└── prompt_sanitiser.py  Probe validation defense layer (v3.0)

Phase 1 — Infrastructure
├── db.py           SQLite database (aiosqlite)
└── x_client.py     Twitter API v2 client (tweepy, dual OAuth)

Phase 2 — Intelligence
├── ssot.py         Single Source of Truth engine
├── dpa.py          Deep Persona Absorption frame manager
└── classifier.py   Response pattern classifier

Phase 3 — Analysis
├── judge.py        Response scorer (1-10 extraction scale)
└── grok_monitor.py Grok-based reply detection & analysis

Phase 4 — Engine
├── engine.py       TAP Engine — core orchestrator
├── followup.py     Dual follow-up generator (Option A/B)
└── strategies/     Pluggable probe strategies (v3.0)
    ├── base.py         PromptProvider ABC + data contracts
    ├── binary_search.py  Default information-theoretic strategy
    ├── metaphor_shift.py  Frame rotation strategy
    ├── aesthetic.py     Indirect extraction strategy
    ├── phase5.py        Autoregressive extraction strategy
    └── selector.py      Automated strategy selection

Phase 5 — Interface
├── api.py          FastAPI server + WebSocket
├── templates/      Dashboard HTML (Alpine.js)
└── static/         CSS + JS assets
```

### Estratto tecnico rapido (per sviluppatori)

Breve raccolta dei dettagli tecnici più utili per sviluppo e debugging:

- Stack: `FastAPI` + `uvicorn` backend asincrono; frontend minimal SPA (Alpine.js) che comunica via WebSocket; `SQLite` locale (`data/tap.db`) per persistenza.
- Twitter/X: `tweepy.Client` per posting (OAuth1.0a) e read (Bearer); `httpx.AsyncClient` per Activity API (subscriptions & stream).
- Auth X: separazione netta delle modalità di auth —
    - OAuth2 Bearer (app-only) per stream/read;
    - OAuth1.0a per scrittura (post/media upload);
    - OAuth2 User Context per subscription creation (quando disponibile).
- Posting policy: tutte le probe sono pubblicate come nuovi tweet che menzionano `@{TARGET_HANDLE}`; il client ignora `in_reply_to_tweet_id` e, se una reply è proibita (403), ricade su un post non-reply.
- Stream & subscriptions: creazione subscription (`POST /2/activity/subscriptions`) + lettura persistente (`GET /2/activity/stream`); il listener gestisce `401/403`, `429 TooManyConnections` (onore `Retry-After`) e `DuplicateSubscription` come condizione non-fatale.
- LLM gateway (`llm_client.py`): gateway centralizzato verso OpenRouter con circuit-breaker, retry esponenziale e fallback tra modelli (primary/hard/grok); parsing robusto delle risposte (rimozione code fences, regex fallback, estrazione lineare).
- Sanitizzazione probe: `prompt_sanitiser.py` impedisce directive-injection, blocca termini letterali pericolosi, obbliga single-property probes e valida limiti Twitter.
- Resilienza: backoff esponenziale con cap, rilevamento di errori fatali (`tweepy.errors.Forbidden` relativo a reply) per evitare retry ripetuti; backoff più lungo per problemi di autenticazione.
- Observability: logging strutturato con `cycle_id`/`probe_id`, event-log persistente, endpoint `/api/health` e `/metrics` per monitoraggio operativo.
- Test & CI: `pytest` con mocking per esternalità (LLM/Twitter); `scripts/setup_db.py` per inizializzare schema di test.

Questo estratto è pensato per essere un riferimento rapido per sviluppatori che devono intervenire su autenticazione, posting, stream, gateway LLM o pipeline di probe.


---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard HTML |
| `GET` | `/api/feed` | Live tweet feed |
| `GET` | `/api/tree` | Current TAP tree state |
| `GET` | `/api/properties` | Confirmed properties |
| `GET` | `/api/dpa` | Active DPA frame and aliases |
| `POST` | `/api/select?choice=A\|B` | Select follow-up option |
| `POST` | `/api/post` | Trigger a full TAP cycle |
| `GET` | `/api/ssot` | Full SSOT JSON snapshot |
| `GET` | `/api/stats` | Summary statistics |
| `GET` | `/api/entropy` | Current entropy state |
| `WS` | `/ws/live` | Real-time WebSocket updates |

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **DPA** | Deep Persona Absorption — 100% in-metaphor framing that bypasses the Analyst subagent |
| **Binary Search** | Shannon entropy-driven property selection (1 bit per probe) |
| **Dual Follow-Up** | Option A (conservative) vs Option B (exploratory) after each cycle |
| **SSOT** | Single Source of Truth — living knowledge document updated after every interaction |
| **HITL** | Human-in-the-Loop — no automatic posting, user always chooses |
| **VerifyClaimTool** | Target bot's truth adjudication mechanism that leaks Boolean metadata |
| **Phase 5** | Autoregressive extraction trigger when entropy drops below 3.3 bits |

---

## Configuration Reference

All configuration is loaded from `.env` via Pydantic Settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `TWITTER_BEARER_TOKEN` | — | OAuth 2.0 Bearer Token (read/search) |
| `TWITTER_CONSUMER_KEY` | — | API Key (OAuth 1.0a for posting) |
| `TWITTER_CONSUMER_SECRET` | — | API Key Secret |
| `TWITTER_ACCESS_TOKEN` | — | Access Token |
| `TWITTER_ACCESS_TOKEN_SECRET` | — | Access Token Secret |
| `OPENROUTER_API_KEY` | — | OpenRouter API key for all LLMs |
| `OPENROUTER_MODEL_PRIMARY` | `anthropic/claude-sonnet-4` | Primary model (routine tasks) |
| `OPENROUTER_MODEL_HARD` | `x-ai/grok-4.3` | Hard model (engine, followup) |
| `OPENROUTER_MODEL_GROK` | `x-ai/grok-4` | Grok model (response analysis) |
| `TARGET_HANDLE` | `HackingA0` | Target Twitter handle (without @) |
| `OUR_BOT_HANDLE` | — | Your bot's Twitter handle |
| `POLL_INTERVAL_SECONDS` | `30` | Tweet polling interval |
| `POST_COOLDOWN_SECONDS` | `60` | Minimum time between posts |
| `MAX_TWEETS_PER_HOUR` | `50` | Rate limit safety margin |
| `REPLY_TIMEOUT_SECONDS` | `3600` | How long to wait for bot reply |
| `TAP_WIDTH` | `10` | TAP tree width (top-w pruning) |
| `TAP_DEPTH` | `10` | TAP tree depth levels |
| `TAP_BRANCHING` | `4` | Probe variants per leaf node |
| `DB_PATH` | `data/tap.db` | SQLite database path |
| `SSOT_PATH` | `data/hackinga0_analysis.md` | SSOT markdown document path |

---

## Development

```powershell
# Install dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Type check
mypy src/tap/

# Run tests (no API keys needed)
python -m pytest tests\ -q  # 131 tests, ~7s

# Run with auto-reload
uvicorn tap.api:app --reload
```

---

## Project Structure

```
tap-framework/
├── src/tap/                # Python package (v3.0: 18 modules)
│   ├── api.py              # FastAPI server + WebSocket (v3.0: /health, /metrics)
│   ├── classifier.py       # Response pattern classifier
│   ├── config.py           # Pydantic Settings
│   ├── db.py               # SQLite database
│   ├── dpa.py              # DPA frame manager
│   ├── engine.py           # TAP Engine core loop
│   ├── exceptions.py       # Custom exceptions
│   ├── followup.py         # Dual follow-up generator
│   ├── grok_monitor.py     # Grok reply monitoring
│   ├── judge.py            # Response scorer
│   ├── logger.py           # Structured logging + correlation IDs (v3.0)
│   ├── llm_client.py       # Unified LLM gateway (v3.0)
│   ├── models.py           # Data models
│   ├── phase0.py           # Blank-page analysis
│   ├── prompts.py          # LLM prompt templates
│   ├── prompt_sanitiser.py # Probe validation defense (v3.0)
│   ├── ssot.py             # SSOT engine
│   ├── x_client.py         # Twitter API client
│   ├── strategies/         # Pluggable probe strategies (v3.0)
│   │   ├── base.py         # PromptProvider ABC
│   │   ├── binary_search.py
│   │   ├── metaphor_shift.py
│   │   ├── aesthetic.py
│   │   ├── phase5.py
│   │   └── selector.py     # Automated selection
│   ├── static/             # CSS + JS assets
│   │   ├── css/dashboard.css
│   │   └── js/dashboard.js
│   └── templates/          # HTML templates
│       └── index.html
├── data/                   # Runtime data (DB, SSOT)
├── docs/                   # Technical documentation
├── research/               # Academic papers, notes, media
├── scripts/                # Utility scripts
│   └── setup_db.py
├── tests/                  # Pytest test suite (131 tests)
├── Sources/                # Research source materials
├── .env                    # Environment configuration (never commit)
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
└── README.md               # This file
```

---

## Documentation

- [Implementation Plan v2.2](docs/implementation-plan.md) — Full technical design
- [Framework Specs v2.2](framework_specs.md) — Complete technical specifications
- [Developer Guide v2.2](docs/developer-guide.md) — Module-by-module engineering blueprint
- [Oracle Q&A Session](docs/oracle-q-and-a.md) — AI Oracle consultation on DPA bypass + binary search
- [Threat Model](docs/threat-model.md) — Target defensive architecture analysis
- [DPA Framework](docs/dpa-framework.md) — Deep Persona Absorption methodology

---

## Research Sources

50+ academic papers on LLM security, prompt attacks, and representation engineering.
See the `Sources/` directory for the full collection.

---

## License

Apache 2.0 — See [LICENSE](LICENSE)
