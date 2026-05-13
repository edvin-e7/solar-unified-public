---
name: API endpoints
description: Full route table for solar-unified backend
updated: 2026-05-04
---

# API endpoints

Mounted in [../../backend/main.py](../../backend/main.py).

## Health + settings

| Method | Path | Owner file | Purpose |
|---|---|---|---|
| GET | `/api/health` | `backend/main.py:86` | liveness + flags + prospect count |
| GET | `/api/settings/flags` | `backend/api/settings.py` | expose `allow_external_llm`, `allow_google_solar_api` |

## Scan + detect

`scan.router` double-mounted as `/api/scan` AND `/api/detect` ([B3 in audit](../sources/2026-04-23-autonomous-progress.md), default-skip).

| Method | Path | Owner file | Purpose |
|---|---|---|---|
| POST | `/api/scan` | `backend/api/scan.py:32` | address → geocode → satellite → Gemini detect |
| POST | `/api/scan/batch` | `:51` | many addresses, best-effort |
| POST | `/api/scan/area` | `:72` | Overpass OSM fetch: `{bbox}` | `{lat,lng,radius_m}` | `{municipality}` → residential houses; optional `enqueue=true` inserts prospects |
| POST | `/api/scan/detect` | `:91` | manual image upload → Gemini |
| POST | `/api/detect` (alias) | same as `/api/scan` | frontend calls this |

## Prospects

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/prospects` | list (filters: `q`, `status`, `min_score`, `max_score`, `limit`) |
| POST | `/api/prospects` | create |
| PUT | `/api/prospects/{id}` | update |
| DELETE | `/api/prospects/{id}` | delete |
| POST | `/api/prospects/bulk-csv` | import |
| POST | `/api/prospects/bulk-status` | batch status update |
| POST | `/api/prospects/bulk-delete` | batch delete |
| POST | `/api/prospects/bulk-geocode` | geocode + solar-potential fill (NOT contact enrichment) |
| GET | `/api/prospects/export/csv` | csv download |
| GET | `/api/prospects/stats` | dashboard metrics |
| POST | `/api/prospects/sort` | sort helper |
| POST | `/api/prospects/route` | regional bucket helper |

## Panels (NEW 2026-04-23)

Owner: `backend/api/panels.py`. Gated on `has_panels=1 AND panel_confidence >= min_confidence`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/panels/catalog` | JSON list, filters: `min_confidence` (default 0.6), `limit` |
| GET | `/api/panels/catalog.xlsx` | xlsx download |
| GET | `/api/panels/stats` | total / high-confidence / contact-enriched counts |

## Solar, Enrich, Agents, Execute

See `backend/api/solar.py`, `enrich.py`, `agents.py`, `executors.py`, `insights.py`.

Key entries:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/solar/potential` | Google Solar + PVGIS fallback |
| POST | `/api/enrich/person` | owner name/age/phone lookup |
| POST | `/api/enrich/batch` | batch enrichment |
| GET | `/api/agents/status` | agent state |
| GET | `/api/agents/leaderboard` | ranking |
| POST | `/api/agents/pitch` | pitch generation |
| GET | `/api/agents/insight` | insight lookup |
| GET | `/api/agents/pattern` | pattern detection |
| GET | `/api/agents/quality` | QA verdict |
| GET | `/api/agents/score` | scoring |
| POST | `/api/execute/cycle` | full agent cycle |
| POST | `/api/execute/learning-only` | learning cycle only |
| GET | `/api/execute/status` | cycle status + count |

## Route count (2026-05-04)

35 routes across `backend/api/*.py` (counted via `grep -rh "@router\." backend/api/`). Health endpoint hardened with DB + env key status.
