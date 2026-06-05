# solar-unified (public showcase)

> ⚠️ **Public showcase version.** Prompt bodies and autonomous-learning data
> are stubbed/abstracted for IP and PII protection. The full implementation
> lives in a private fork maintained by the author. This snapshot is published
> as an architecture showcase, not a turnkey product.

Swedish solar-prospecting system: take an address, pull rooftop satellite
imagery, detect whether panels are already installed, score the lead, and
draft an outreach pitch — coordinated by a small set of prompt-driven agents
with a verification gate and a self-improving prompt loop.

Built to run **zero-cost by default**: free geocoding (Nominatim), free
imagery (ArcGIS World Imagery), and local vision/text via Ollama. Paid APIs
(Google Solar, external Gemini) are env-gated **off** by default so you never
get surprise billing.

## What this demonstrates

- **Multi-agent coordinator** (`backend/agents/coordinator.py`) orchestrating
  six specialised agents — `detection`, `scoring`, `pitch`, `pattern`,
  `quality`, `ui_design` — over a shared journal, with a leaderboard and
  per-agent action tracking.
- **Pluggable panel-detection pipeline** with an `auto` dispatcher that picks
  the first available backend: trained ML head (`embed` / `ml`) → local vision
  LLM (`moondream` via Ollama) → paid Gemini Vision (gated). See
  `backend/services/detection_*.py`.
- **CoVe-style verification gate** (`backend/cove_verifier.py`,
  `backend/agents/verification.py`) that re-checks `AUTO_FULL` agent decisions
  before they take effect.
- **Issue Ledger** (`backend/issue_ledger.py`) — cross-session memory keyed on
  `(error_type, target)`, so the autonomous loop stops re-trying fixes that
  already failed.
- **Autonomous-learning loop** (`backend/autonomous_learner.py`,
  `backend/self_improve.py`) that proposes prompt edits; the CoVe verifier
  accepts/rejects and the learning journal records the outcome.
- **Spec-first testing** — every backend module has a paired spec in
  `backend/specs/` (Markdown spec + `test_*.py`).
- **FastAPI backend** + **React 19 / Vite** frontend, packaged for desktop
  (Electron) and Android (Capacitor).

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Python ≥ 3.11 |
| Frontend | React 19 + Vite + Tailwind 4, MapLibre GL |
| Desktop / mobile | Electron, Capacitor (Android) |
| Text LLM | Ollama (local default), Gemini (opt-in, gated) |
| Vision | Moondream via Ollama, ONNX detection head, optional Gemini Vision |
| Geo / imagery | Nominatim (OSM), ArcGIS World Imagery; PVGIS for solar potential |
| Storage | SQLite, JSONL journals |
| Deploy | Docker Compose |

## Quickstart

Requirements: Python ≥ 3.11, [pnpm](https://pnpm.io/), and (recommended)
[Ollama](https://ollama.com) for free local LLM + vision.

```bash
cp .env.example .env
# Defaults are free/local: ALLOW_GOOGLE_SOLAR_API=0, ALLOW_EXTERNAL_LLM=0,
# LLM_PROVIDER=ollama, DETECTION_BACKEND=auto.

make install        # backend venv + frontend pnpm deps
make ml-moondream   # optional: pull the local vision model (~1.5 GB)
make dev            # backend on :8000, frontend on :5173
```

To run components by hand instead of `make`:

```bash
# Backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate shell)
cd frontend
pnpm install
pnpm dev
```

The backend checks for `GEMINI_API_KEY` at startup. It is **not** required to
boot keyless / fully local — set `ALLOW_BOOT_WITHOUT_KEYS=1` (the
`make dev-android` target does this automatically). `GOOGLE_MAPS_API_KEY` is
only needed when `ALLOW_GOOGLE_SOLAR_API=1`.

See `docs/DEPLOY.md` for production deployment and `docs/QA_MANUAL.md` for the
end-to-end manual test path.

## Detection backends

Set via `DETECTION_BACKEND` in `.env`:

| Value | Backend | Cost |
|---|---|---|
| `auto` (default) | `ml` → `embed` → `moondream` → `gemini`, first available wins | free unless it falls through to `gemini` |
| `embed` | trained mobilenet head (`backend/models/head.npz`) | free |
| `ml` | YOLOv8-seg ONNX (drop your own model file) | free |
| `moondream` | local Ollama vision LLM | free |
| `gemini` | Gemini Vision | paid — requires `ALLOW_EXTERNAL_LLM=1` |

ML helper targets: `make ml-encoder`, `make ml-train`, `make ml-eval`,
`make ml-test`, `make ml-bootstrap-labels`.

## API surface

FastAPI app (`backend/main.py`) mounts routers under `/api`:
`/api/scan`, `/api/detect`, `/api/leads`, `/api/solar`, `/api/enrich`,
`/api/prospects`, `/api/panels`, `/api/agents`, `/api/execute`,
`/api/settings`. Interactive docs at `http://localhost:8000/docs`.

## Architecture write-ups

- `PRD.md` — product requirements
- `docs/AUTONOMOUS_TRAINING.md` — how the self-improvement loop works
- `docs/ISSUE_LEDGER.md` — cross-session debugging memory pattern
- `docs/BEST_OUTCOME_STRATEGY.md` — pipeline-design decisions
- `docs/SWEDISH_APIS_REFERENCE.md` — geo/data sources used for the SE market
- `docs/DEPLOY.md` / `docs/BACKUP.md` — deployment + backup/restore
- `wiki/` — concepts, entities (API endpoints, schema), and goal progress

## Prompts & learning data

The `backend/prompts/*.md` files in this public version are **stubs** (the
loader convention is in `backend/prompts_loader.py`). To run your own
deployment, replace each stub with real Markdown. The autonomous-learning
output directory (`backend/prompts/learned/`, which holds prospect-derived
data) is **not** included — the loop starts fresh on a new deployment.

## Privacy & data handling

Solar prospecting touches personal data (property addresses, registered
owners). This codebase processes that locally and avoids logging full records.
`backend/data/` and `private/` are gitignored and contain no data in this
public repo.

## License

MIT — see `LICENSE`. The trained detection head under `backend/models/` has
its own license note (`backend/models/LICENSE.md`).

## Author

[Edvin Pierre](https://github.com/edvin-e7) — built as a personal project to
bootstrap a Swedish solar-lead bureau. The private fork carries the full
commit history, real prompts, and deployment-specific config. This public
snapshot keeps the architecture visible.

## Status

Snapshot from active development, published as a fresh-init showcase. It is not
guaranteed to be production-ready end-to-end; expect rough edges and stubbed
prompt content. Issues and PRs are welcome, but the author's priority is the
private backlog.
