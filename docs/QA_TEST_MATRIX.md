# QA Test Matrix

Cross-reference of every shipped feature → page it lives on → endpoint it calls → manual-QA test ID in `QA_MANUAL.md`.

Run the full matrix at least once per milestone. Run affected rows before every UI/API commit.

| Feature | Page | Endpoint | QA tests |
|---|---|---|---|
| KPI tiles | Dashboard | GET /api/prospects/stats | T-01 |
| Daily bars | Dashboard | GET /api/prospects/stats | T-02 |
| Agent activity feed | Dashboard | GET /api/agents/status | T-03 |
| Pull-quote insight | Dashboard | GET /api/agents/insight | T-04 |
| Add prospects (paste) | Prospekt | POST /api/prospects | T-10 |
| Add prospects (CSV) | Prospekt, Inställningar | POST /api/prospects/bulk-csv | T-11, T-37 |
| List prospects | Prospekt | GET /api/prospects | T-12 |
| Select prospect | Prospekt | — | T-13 |
| Bulk status change | Prospekt | POST /api/prospects/bulk-status | T-14 |
| Bulk delete | Prospekt | POST /api/prospects/bulk-delete | T-15 |
| Bulk enrich | Prospekt, Berikning | POST /api/prospects/bulk-enrich | T-16, T-31 |
| Status hotkeys 1-4 | Prospekt | POST /api/prospects/bulk-status | T-17 |
| J/K row nav | Prospekt | — | T-18 |
| Info / Anteckningar / Dokument tabs | Prospekt, Karta | — | T-19, T-25 |
| Export CSV | Prospekt, Inställningar | GET /api/prospects/export/csv | T-20, T-38 |
| Filter search | Sök | GET /api/prospects?q=… | T-21 |
| Saved searches | Sök | localStorage | T-22 |
| Detect panels | Detektion | POST /api/detect | T-23 |
| CoVe votes | Detektion | POST /api/detect | T-24 |
| Map pins colored by status | Karta | GET /api/prospects | T-25 |
| Map pin → drawer | Karta | — | T-26 |
| Live agent status | Agenter | GET /api/agents/status | T-27 |
| Leaderboard | Agenter | GET /api/agents/leaderboard | T-28 |
| Journal tail | Agenter | GET /api/execute/status | T-29 |
| Run learning cycle | Agenter | POST /api/execute/learning-only | T-30 |
| Gate status chips | Berikning, Inställningar | GET /api/settings/flags | T-31, T-35 |
| Theme toggle | Inställningar | localStorage | T-34 |
| Hotkey reference table | Inställningar | — | T-36 |
| Offline banner | all | heartbeat /api/agents/status | T-40 |

Any feature not in this matrix is considered unsupported — add a row or delete the feature.
