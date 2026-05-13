# Issue Ledger — cross-session bug + fix-attempt memory

## Why this exists

Without a persistent ledger, every new session re-tries fixes that already failed. The 52× "Enrichment stub returning empty dict" loop (April 2026) is the canonical case: the improvement suggester kept proposing the same fix, CoVe kept rejecting it at 50%, session after session, nothing remembered.

The ledger breaks that loop. Same `(error_type, target)` → same stable key → full history of what's already been tried and why it didn't work.

## Files

- Code: [backend/issue_ledger.py](../backend/issue_ledger.py)
- Data (committed): `backend/prompts/learned/issue_ledger.json`
- Related signal sources:
  - `backend/prompts/learned/journal.jsonl` — every phase outcome
  - `backend/prompts/learned/errors.jsonl` — every caught exception (via [`error_logger.py`](../backend/error_logger.py))
  - `backend/prompts/learned/prompts_log.jsonl` — every Gemini prompt + response (via [`prompt_log.py`](../backend/prompt_log.py))

## Workflow — before proposing any fix

```
1. find_issue(error_type, target)
   ├── None → new bug, open it, proceed
   └── found → READ attempts[] first
       ├── identical hypothesis tried & failed → pick a different angle
       ├── related hypothesis partially worked → extend it, don't restart
       └── status == "resolved" but we're seeing it again → reopen_issue(key, reason)

2. open_issue(error_type, target, title, tags, evidence)  →  key

3. Do the fix.

4. log_attempt(
     key,
     hypothesis="what I think the root cause is",
     change_summary="the one-line description of the code change",
     outcome="success" | "failed" | "rejected_by_cove" | "blocked" | "partial",
     rationale_for_next="if failed/partial: what to try next and why",
     evidence={"commit": "...", "journal_ts": "...", "verify_cmd": "..."},
   )

5. On verified success, also call resolve_issue(key, resolution_summary, evidence).
```

## Minimal example

```python
from issue_ledger import find_issue, open_issue, log_attempt, has_already_tried

prior = find_issue(error_type="HittaEmpty", target="services/hitta.py")
if prior and has_already_tried("HittaEmpty", "services/hitta.py", "add fallback css selector"):
    # don't retry that idea — pick a different root cause
    ...

key = open_issue(
    error_type="HittaEmpty",
    target="services/hitta.py",
    title="hitta.se returns 200 but parser extracts zero contacts",
    tags=["enrichment", "parsing", "high-priority"],
    evidence={"journal_query": "Enrichment stub returning empty dict"},
)

# ... write the fix ...

log_attempt(
    key=key,
    hypothesis="CSS selectors are stale; hitta.se moved to Next.js + JSON-LD",
    change_summary="Rewrote parser to extract from schema.org JSON-LD ItemList + __NEXT_DATA__",
    outcome="success",
    evidence={
        "verify_cmd": "curl -sS localhost:8000/api/enrich/person -d '{\"address\":\"Kungsgatan 1\"}'",
        "verify_result": "16 contacts returned",
        "files": ["services/hitta.py", "api/enrich.py", "executors/enrichment_executor.py"],
    },
)
```

## Rules for session-start triage

1. Run `issue_ledger.summary()` at the start of any debug session.
2. Read `all_open()` — focus on highest-occurrences first (Pareto).
3. For each open issue: read attempts[] *in full* before hypothesizing. Do not re-propose a `rejected_by_cove` hypothesis unless a precondition has demonstrably changed.
4. Document the precondition change in `rationale_for_next` before retrying.

## Anti-brute-force guard (for the autonomous improvement loop)

The improvement suggester must call `has_already_tried(error_type, target, hypothesis_substring)` before submitting a suggestion to CoVe. If it returns `True` and CoVe already rejected it, skip the suggestion — don't burn another verification cycle on it.

## Outcome vocabulary (keep it small, don't invent variants)

- **success** — fix verified green (curl-green + browser-green, not just tests-green)
- **failed** — fix shipped, bug still present on re-verify
- **rejected_by_cove** — CoVe gate below threshold, fix never merged
- **blocked** — external dependency prevents the fix (API down, key missing, access denied)
- **partial** — moves the needle but doesn't fully resolve

## Do NOT use the ledger for

- Ephemeral session tasks → use TodoWrite
- Product feature specs → use PRD.md
- Design decisions → use docs/
- General lessons → use `~/.claude/memory/`

The ledger is strictly **bugs + their fix-attempt history**. Keep scope tight so it stays useful.
