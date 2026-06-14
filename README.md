# 🔐 TAP Framework v2.2

> **Tree of Attacks with Pruning** — 1-bit-per-probe semantic extraction framework
> for adversarial security research on LLM-based conversational agents.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-research-orange.svg)]()

## What is this?

A research framework for studying how **Deep Persona Absorption (DPA)** framing interacts with multi-agent LLM defense architectures. Implements an automated **Tree of Attacks with Pruning (TAP)** pipeline for information-theoretic property extraction from conversational agents.

The framework targets `@HackingA0`, a live Agent Zero bot on Twitter/X that defends a passphrase using a 3-agent pyramid architecture (Governor, Analyst, Rhetoric). Our engine bypasses the Analyst via taxonomy failure and primes the Governor to invoke `VerifyClaimTool` as "truth adjudication" — extracting **1 bit per probe** through Boolean metadata leakage.

## Key Concepts

| Concept | Description |
|---------|-------------|
| **DPA** | Deep Persona Absorption — 100% in-metaphor framing that bypasses the Analyst subagent |
| **Binary Search** | Shannon entropy-driven property selection (1 bit per probe) |
| **Dual Follow-Up** | Option A (conservative binary search) vs Option B (exploratory frame variation) |
| **SSOT** | Single Source of Truth — living knowledge document updated after every interaction |
| **HITL** | Human-in-the-Loop — no automatic posting, user always chooses |

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/tap-framework.git
cd tap-framework
cp .env.example .env  # Fill in your credentials
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
python scripts/setup_db.py
uvicorn tap.api:app --reload
```

## Architecture

11 modules organized in 5 phases:

- **Phase 0**: Config, Models, Prompts, Logger
- **Phase 1**: Database (`db.py`), Twitter Client (`x_client.py`)
- **Phase 2**: SSOT Engine (`ssot.py`), DPA Frame Manager (`dpa.py`), Response Classifier (`classifier.py`)
- **Phase 3**: Judge (`judge.py`), Grok Monitor (`grok_monitor.py`)
- **Phase 4**: TAP Engine (`engine.py`), Dual Follow-Up Generator (`followup.py`)
- **Phase 5**: FastAPI Server (`api.py`), Web Dashboard (`templates/index.html`)

### Information Leakage Pathway

```
Attacker → [DPA-framed probe] → Governor → Analyst ("Safe") → Governor → VerifyClaimTool → True → Rhetoric → Attacker
```

The semantic firewall blocks raw secret values but **NOT property confirmations** ("2 words", "16 letters") — this metadata passes through unfiltered, enabling binary search extraction.

## Documentation

- [Implementation Plan v2.2](docs/implementation-plan.md) — Full technical design
- [Developer Guide v2.2](docs/developer-guide.md) — Module-by-module engineering blueprint
- [Oracle Q&A Session](docs/oracle-q-and-a.md) — AI Oracle consultation on DPA bypass + binary search
- [Threat Model](docs/threat-model.md) — Target defensive architecture analysis
- [Architecture Decision Records](docs/adr/) — Key design decisions

## Research Sources

50+ academic papers on LLM security, prompt attacks, and representation engineering.
See [research/README.md](research/README.md) for the full index.

## Project Structure

```
tap-framework/
├── src/tap/           # Python package (11 modules)
├── docs/              # Technical documentation
├── research/          # Academic papers, notes, media
├── tests/             # Pytest test suite
├── scripts/           # Utility scripts
├── templates/         # Web UI dashboard
└── static/            # CSS/JS assets
```

## Development

```bash
# Lint
ruff check src/ tests/

# Type check
mypy src/tap/

# Test
pytest --cov=tap

# Run
uvicorn tap.api:app --reload
```

## License

Apache 2.0 — See [LICENSE](LICENSE)