GitHub repository plan created at `.ignore.workinprogress/github_repository_plan.md`.

## Repository: `tap-framework` v2.2.0

### Structure Overview

| Directory | Contents | Source |
|-----------|----------|--------|
| `docs/` | Implementation plan, developer guide, Oracle Q&A, threat model, ADRs | From `.ignore.workinprogress/` |
| `src/tap/` | 11 Python modules (config → api) | From developer guide module specs |
| `research/sources/` | 50 academic papers (MD) | From `Sources/` |
| `research/notes/` | 8 synthesized analysis notes | From `Notes/` |
| `research/quizzes/` | 2 knowledge maps (JSON) | From `Quizzes/` |
| `research/media/` | Audio, infographics, video | From `Audio/`, `Infographics/`, `Videos/` |
| `tests/` | Pytest suite for all modules | New |
| `scripts/` | DB setup, SSOT bootstrap, env verification | New |
| `.github/` | CI workflow (lint+test), issue templates | New |

### Key Design Decisions

- **License**: Apache 2.0 (research-friendly)
- **Python**: 3.11+ with `pyproject.toml` (PEP 621)
- **Branching**: `main` (stable) + `develop` (integration) + feature branches
- **Commits**: Conventional commits (`feat(dpa):`, `docs(guide):`, etc.)
- **CI**: GitHub Actions with ruff + mypy + pytest on Python 3.11/3.12
- **Media**: Git LFS for `.mp3`, `.mp4`, `.png` files
- **Secrets**: All gitignored; `.env.example` template only

### 5 Milestones

1. **Foundation** (Week 1-2): config, models, db, x_client
2. **Intelligence** (Week 3-4): ssot, dpa, classifier
3. **Attack Core** (Week 5-6): judge, grok, engine, followup
4. **Interface** (Week 7-8): api, dashboard, HITL workflow
5. **Research** (Ongoing): ADRs, API docs, paper index

### Execution Commands

```bash
gh repo create tap-framework --public
git init && git lfs install
# Create structure, move files per mapping table
git add . && git commit -m "feat: initial repository structure with research materials"
git push -u origin main
git checkout -b develop && git push -u origin develop
```