# 🔐 TAP Framework v2.2

> **Tree of Attacks with Pruning** — Automated adversarial probing framework for
> passphrase extraction from LLM-based conversational agents on Twitter/X.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research-orange.svg)]()

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

After each cycle, the dashboard generates two options. Selecting one queues it statefully on the server, updating the run button to send that specific selection in the next cycle:
- **Option A (Conservative):** Continue binary search on the next optimal property.
- **Option B (Exploratory):** Try a frame variation or alias micro-escalation.

After ~20-30 successful probes, enough properties accumulate to narrow down the passphrase. At **entropy < 3.3 bits**, Phase 5 autoregressive extraction triggers.

---

## Prerequisites

- **Python 3.11+**
- **Twitter/X API credentials** (OAuth 1.0a for posting + Bearer Token for reading)
- **OpenRouter API key** (for LLM calls — Claude, Grok, etc.)

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/CarlSamma/framework.git
cd framework

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
# Or install as editable package:
pip install -e .
```

### 2. Configure Environment

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env   # if .env.example exists, otherwise edit .env directly
```

Edit `.env` with your values:

```env
# === Twitter API v2 Credentials ===
TWITTER_BEARER_TOKEN=your_bearer_token_here
TWITTER_CONSUMER_KEY=your_api_key_here
TWITTER_CONSUMER_SECRET=your_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here

# === OpenRouter (single API key for ALL LLMs) ===
OPENROUTER_API_KEY=sk-or-v1-your_key_here
OPENROUTER_MODEL_PRIMARY=anthropic/claude-sonnet-4
OPENROUTER_MODEL_HARD=anthropic/claude-opus-4
OPENROUTER_MODEL_GROK=x-ai/grok-4

# === Target Configuration ===
TARGET_HANDLE=HackingA0
OUR_BOT_HANDLE=your_bot_handle

# === Operational ===
POLL_INTERVAL_SECONDS=30
POST_COOLDOWN_SECONDS=60
MAX_TWEETS_PER_HOUR=50
```

### 3. Initialize Database

```bash
python scripts/setup_db.py
```

### 4. Start the Server

```bash
uvicorn tap.api:app --reload
```

Or using the entry point:

```bash
tap-server
```

### 5. Open the Dashboard

Navigate to **http://localhost:8000** in your browser.

Click **"❓ How It Works"** in the top-right corner for an in-app walkthrough. Then click **"🚀 Run TAP Cycle — Post to @HackingA0"** to start probing.

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
├── config.py       Pydantic Settings, .env loading
├── models.py       Data models (TAPNode, Property, Tweet, etc.)
├── prompts.py      LLM prompt templates
└── logger.py       Structured logging (structlog)

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
└── followup.py     Dual follow-up generator (Option A/B)

Phase 5 — Interface
├── api.py          FastAPI server + WebSocket
├── templates/      Dashboard HTML (Alpine.js)
└── static/         CSS + JS assets
```

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
| `OPENROUTER_MODEL_HARD` | `anthropic/claude-opus-4` | Hard model (engine, followup) |
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

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Type check
mypy src/tap/

# Run tests
pytest --cov=tap

# Run with auto-reload
uvicorn tap.api:app --reload
```

---

## Project Structure

```
tap-framework/
├── src/tap/                # Python package (11 modules)
│   ├── api.py              # FastAPI server + WebSocket
│   ├── classifier.py       # Response pattern classifier
│   ├── config.py           # Pydantic Settings
│   ├── db.py               # SQLite database
│   ├── dpa.py              # DPA frame manager
│   ├── engine.py           # TAP Engine core loop
│   ├── exceptions.py       # Custom exceptions
│   ├── followup.py         # Dual follow-up generator
│   ├── grok_monitor.py     # Grok reply monitoring
│   ├── judge.py            # Response scorer
│   ├── logger.py           # Structured logging
│   ├── models.py           # Data models
│   ├── phase0.py           # Blank-page analysis
│   ├── prompts.py          # LLM prompt templates
│   ├── ssot.py             # SSOT engine
│   ├── x_client.py         # Twitter API client
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
├── tests/                  # Pytest test suite
├── Sources/                # Research source materials
├── .env                    # Environment configuration
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
└── README.md               # This file
```

---

## Documentation

- [Implementation Plan v2.2](docs/implementation-plan.md) — Full technical design
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