---
name: Deploy via systemd
description: solar-unified.service — production-localhost deployment unit + env wiring
updated: 2026-04-23
---

# Deploy via systemd

The backend runs as a long-lived service on Edvin's Chromebook Crostini:

## Unit

```
/lib/systemd/system/solar-unified.service
```

```ini
[Unit]
Description=Solar Unified Backend Service
After=network.target

[Service]
Type=simple
User=edvinpierre03
WorkingDirectory=/opt/solar-unified/backend
ExecStart=/opt/solar-unified/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
EnvironmentFile=/etc/solar-unified/backend.env

[Install]
WantedBy=multi-user.target
```

## Env file

```
/etc/solar-unified/backend.env
```

Holds:
- `GEMINI_API_KEY` — **must be real, not placeholder**
- `GOOGLE_MAPS_API_KEY`
- `PORT=8000`
- `ALLOW_GOOGLE_SOLAR_API=1`
- `ALLOW_EXTERNAL_LLM=1`
- `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`

Ownership: `edvinpierre03:edvinpierre03` (unusual for `/etc/` but already set — no sudo required to edit).

## Deploy snapshot

`/opt/solar-unified/` is a stripped snapshot of `~/solar-unified/` (137M vs 4.1G). Key differences:
- No `.git`, no `docs/`, no `frontend/node_modules`
- Contains `.venv/` in `backend/`
- No `.env` files at root or `backend/` — env comes from systemd EnvironmentFile

## Sync workflow (dev → deploy)

```bash
# edit in ~/solar-unified source tree
cp ~/solar-unified/backend/PATH /opt/solar-unified/backend/PATH
sudo systemctl restart solar-unified
sleep 3
curl -sS http://127.0.0.1:8000/api/health
```

## Restart runbook

```bash
sudo systemctl restart solar-unified
journalctl -u solar-unified --no-pager -n 50 | tail -50  # check for errors
curl -sS http://127.0.0.1:8000/api/health  # expect {"status":"ok",...}
```

## Known incident (2026-04-23)

`/etc/solar-unified/backend.env` had `GEMINI_API_KEY=your_api_key_here` (placeholder). All Gemini calls failed 400 INVALID_ARGUMENT. Masked as 200 OK + empty result by `scanner.py` silent-fail. Root-cause fix:
1. Real key written to env file
2. `scanner.py` raises RuntimeError on Gemini failure → `scan.py` → HTTPException(502)
3. systemd restart

See [log.md](../log.md) 2026-04-23 entries.
