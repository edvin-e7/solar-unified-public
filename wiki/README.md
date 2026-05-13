---
name: solar-unified wiki
description: Project-internal satellite wiki; inherits schema from ~/wiki
updated: 2026-04-23
---

# solar-unified/wiki — satellite

Repo-internal technical knowledge base. Schema: [../../wiki/SCHEMA.md](../../wiki/SCHEMA.md).

Cross-project goals + user entity live at [~/wiki/](../../wiki/). This satellite covers **repo-internal** details:

- [index.md](./index.md) — page catalog
- [log.md](./log.md) — phase/change log (complements `backend/prompts/learned/journal.jsonl`)
- [goals/](./goals/) — project-scoped goals + U0-U11 progress
- [entities/](./entities/) — endpoints, schema, deploy unit
- [concepts/](./concepts/) — patterns (detection pipeline, learning loop)
- [sources/](./sources/) — briefs, RFCs, design docs

## Run quickstart

```bash
make install     # venv + pnpm i
make dev         # uvicorn :8000 + vite :5173
make verify      # scripts/verify_all.py
```

Deploy: systemd `solar-unified.service` reads `/etc/solar-unified/backend.env`.

## Known gotcha (filed 2026-04-23)

`/etc/solar-unified/backend.env` must hold real Gemini key — placeholder causes silent Gemini failure → pseudosuccess. See [entities/deploy-systemd.md](./entities/deploy-systemd.md).
