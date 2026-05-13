---
name: Prospects schema
description: SQLite table definition, migrations, indexes for prospects table
updated: 2026-04-23
---

# Prospects schema

Owner: [`backend/api/prospects.py`](../../backend/api/prospects.py).
DB: `backend/data/prospects.db` (git-ignored per PII rule).

## Current schema (2026-04-23, after U1)

```sql
CREATE TABLE prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    lat REAL,
    lng REAL,
    status TEXT DEFAULT 'new',
    score REAL,
    annual_kwh REAL,
    owner_name TEXT,
    owner_age INTEGER,
    owner_phone TEXT,
    notes TEXT,
    has_panels INTEGER,           -- NEW U1: 0/1 (nullable)
    panel_confidence REAL,        -- NEW U1: 0.0-1.0
    detected_at TEXT,             -- NEW U1: ISO-8601 UTC
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

## Indexes

```sql
CREATE INDEX idx_prospects_status ON prospects(status);
CREATE INDEX idx_prospects_score ON prospects(score DESC);
CREATE INDEX idx_prospects_has_panels ON prospects(has_panels);  -- NEW U1
```

## Migration pattern

`_migrate()` runs on every `db()` context-manager enter:

1. `PRAGMA table_info(prospects)` → existing column set
2. For each required column in `_PANEL_COLUMNS`, `ALTER TABLE ... ADD COLUMN` if missing
3. `CREATE INDEX IF NOT EXISTS idx_prospects_has_panels` (after ALTER, not in SCHEMA script)

**Lesson**: CREATE INDEX in SCHEMA-script fails when referencing column that only ALTER will add. Keep index creation in `_migrate()` after ALTERs. ([phase journal 2026-04-23](../log.md))

## Status values

- `new`, `interested`, `callback`, `rejected` (enforced in `bulk-status` endpoint, not DB)

## Panel-catalog query

```sql
SELECT * FROM prospects
WHERE has_panels = 1
  AND COALESCE(panel_confidence, 0) >= ?
ORDER BY panel_confidence DESC NULLS LAST,
         detected_at DESC NULLS LAST
LIMIT ?
```

Used by [API endpoints](./api-endpoints.md) `/api/panels/catalog`.

## Current row count (2026-04-23)

6378 rows. Of these:
- 1 with `has_panels` populated (Kungsgatan 15 scan post-U1)
- 6377 imported pre-U1 → `has_panels` NULL

Backfill decision pending in [u0-u11-progress goal](../goals/u0-u11-progress.md).
