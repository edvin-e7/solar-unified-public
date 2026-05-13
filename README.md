# solar-unified (public showcase)

> ⚠️ **Public showcase version.** Prompts and autonomous-learning data are
> abstracted for IP and PII protection. Full implementation lives in a
> private fork by the maintainer.

Autonomous Swedish solar-prospecting system. Multi-agent coordinator, ML
panel detection, CoVe-verified pipeline, self-modifying prompt loop.

## What this demonstrates

- **Multi-agent coordinator pattern** orchestrating specialised agents
  (analyser, pitcher, verifier) over a shared journal.
- **ML-based panel detection** combining ONNX model + Moondream
  (local vision LLM) on rooftop satellite imagery from ArcGIS Sweden.
- **CoVe-style verification gate** that catches autonomous-learning
  regressions before they reach production prompts.
- **Issue Ledger pattern** — cross-session memory of fix attempts (key:
  `(error_type, target)`) breaks the loop of re-trying solutions that
  already failed.
- **FastAPI backend** + **React 19 + Electron** desktop app.
- **Prompt-driven agents** with versioned prompt files and structured
  logging (`prompt_log.py`, `error_logger.py`, `learning_journal.py`).
- **Autonomous-learning loop** — `autonomous_learner.py` + `self_improve.py`
  propose prompt edits, CoVe verifier accepts/rejects, journal records
  outcome.

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + Python 3.11+ |
| Desktop | React 19 + Vite + Electron |
| LLM | Gemini API (opt-in), Ollama (local default) |
| Vision | Moondream (Ollama) + ONNX local model |
| Geo | ArcGIS World Imagery, Nominatim (OpenStreetMap) |
| Storage | SQLite, JSONL journals |
| Deploy | Docker Compose, Cloudflare Tunnel |

## Running

See `docs/DEPLOY.md` for the full deployment guide. Quick local dev:

```bash
cp .env.example .env
# Edit .env: set ALLOW_GOOGLE_SOLAR_API=0 (default — no paid APIs)

# Backend
cd backend
pip install -r requirements.txt
ollama pull moondream
python -m uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Architecture write-ups

- `PRD.md` — Product Requirements Document
- `docs/AUTONOMOUS_TRAINING.md` — how the self-improvement loop works
- `docs/ISSUE_LEDGER.md` — cross-session memory pattern for debugging
- `docs/BEST_OUTCOME_STRATEGY.md` — pipeline-design decisions
- `docs/BACKUP.md` — backup + restore approach
- `docs/DEPLOY.md` — production deployment

## Prompts

The `backend/prompts/*.md` files in this public version are stubs. The full
prompt content is private. To run your own deployment, replace each stub
with Markdown following the loader convention in `backend/prompts_loader.py`.

The `backend/prompts/learned/` directory (autonomous-learning data with
prospect PII) is excluded entirely. The autonomous loop will start fresh
on a new deployment.

## Privacy & data handling

Solar prospecting touches personal data (property addresses, registered
owners). This codebase processes that data locally and never logs full
records. See `SECURITY.md` for the threat model.

## License

MIT (see `LICENSE`).

## Author

[Edvin Pierre](https://github.com/edvin-e7) — built as part of a personal
project to bootstrap a Swedish solar-lead bureau. The private fork
includes maintainer-specific prompts, real prospect data, and
deployment-specific configuration. This public showcase keeps the
architecture visible.

## Status

This is a snapshot from active development. The private fork has the full
241-commit history and moves faster. This public version is a fresh-init
snapshot intended as an architecture showcase — pull requests and issues
welcome here, but priority goes to the private backlog.
