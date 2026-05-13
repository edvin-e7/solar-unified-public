---
name: U0-U11 autonomous progress
description: Live status of the 2026-04-23 autonomous fix pass
updated: 2026-04-23
status: in-progress
mirror: /home/user/AUTONOMOUS_PROGRESS.md
brief: /home/user/AUTONOMOUS_FIX_BRIEF_2026-04-23.md
---

# U0-U11 autonomous progress

Mirror of [~/AUTONOMOUS_PROGRESS.md](file:///home/user/AUTONOMOUS_PROGRESS.md). Goal-level: [../../../wiki/goals/solar-panel-catalog.md](../../../wiki/goals/solar-panel-catalog.md).

## Task matrix

| # | Task | Status | Evidence |
|---|---|---|---|
| U0 | Diagnose localhost | ✅ | systemd env placeholder key; fix + scanner.py raise; `/api/detect` → `conf=0.9` real reasoning |
| U1 | Schema `has_panels`/`panel_confidence`/`detected_at` | ✅ | `PRAGMA table_info` shows cols 13-15; new scan populates all three |
| U2 | `/api/panels/catalog` + `.xlsx` + `/stats` | ✅ | All 200; xlsx binary = PK-header valid archive |
| W1 | `~/wiki/` hub | ✅ | SCHEMA + README + index + log + goals + entities + sources seeded |
| W2 | `solar-unified/wiki/` satellite | ✅ | README + index + log + entities + concepts + goals |
| W3 | Stub wikis in other 4 repos | ⏳ | Pending |
| W4 | CLAUDE.md wiki-references | ⏳ | Pending |
| W5 | git init `~/wiki/` | ⏳ | Pending |
| U3 | Frontend panel-catalog page + nav | ⏳ | Pending |
| U4 | env_file/health/CORS verification | 🟡 | systemd done; docker-compose config check pending |
| U5 | `/api/scan/area` Overpass | ⏳ | Pending |
| U6 | Drop `/api/detect` alias | ⏭️ | Default-skip (optional per brief) |
| U7-U10 | Per-repo cleanup | ⏳ | Pending |
| U11 | Simplify + slutrapport | ⏳ | Pending |

## Blockers

- 6377 pre-U1 prospects have `has_panels=NULL`. Decision: backfill (from `notes` JSON) or accept forward-only coverage?
- Playwright not yet installed for UX smoke — will need `pnpm exec playwright install chromium` before U3 end-to-end test.

## Next action

Finish W3-W5 (stubs + CLAUDE.md + git), then U3 frontend page.
