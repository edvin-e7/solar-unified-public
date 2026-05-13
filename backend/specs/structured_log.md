# Spec: `structured_log` primitive

**Kontrakt**: en modul, ett append, ett atomiskt skriv. Varje jsonl-logg i projektet (`errors.jsonl`, `prompts_log.jsonl`, `journal.jsonl`) OCH json-state-filen `issue_ledger.json` routas genom denna. Ingen annan modul öppnar filerna direkt.

## Why

Audit (2026-04-24) visade att `error_logger`, `prompt_log`, `issue_ledger`, `learning_journal` var och en implementerade egen "öppna-fil-och-skriv"-logik. Resultat: inga är atomiska, inga har PII-hook, inga är async-säkra, `log_and_swallow` brustet på async, `issue_ledger._save` mid-write-crash = korrumperad JSON (= förlorad anti-brainrot-historia).

Enda korrekta fix: EN primitiv, hardad en gång, med matris som kvarstannar. Alla logg-moduler tunnas till callers.

## Public API

```python
from typing import Awaitable, Callable, Mapping
from pathlib import Path

# JSONL-append — atomic, async-safe, crash-safe.
async def append_jsonl(
    path: Path,
    record: Mapping[str, object],
    *,
    redact: Callable[[dict], dict] | None = None,
) -> None: ...

# JSONL-append, sync equivalent (for sync callers, e.g. learning_journal.record called from sync code).
def append_jsonl_sync(
    path: Path,
    record: Mapping[str, object],
    *,
    redact: Callable[[dict], dict] | None = None,
) -> None: ...

# JSON-state write — atomic whole-file rewrite.
def write_json_atomic(
    path: Path,
    data: object,
    *,
    redact: Callable[[dict], dict] | None = None,
) -> None: ...

# Sanity on reload — drop stale `.tmp` siblings from prior crashes.
def cleanup_stale_tmp(path: Path) -> None: ...
```

## Invariants

1. **Atomicity** — `write_json_atomic` writes to `<path>.tmp` + `os.replace()`. Reader never sees a half-written file. On crash mid-write, `.tmp` may linger; `cleanup_stale_tmp` removes it on next load.
2. **Append-line integrity** — `append_jsonl` writes exactly one line per call via a single `write(bytes)` call (bytes < 4 KiB; larger records split is ERROR, not a corruption risk). Single POSIX write = atomic at kernel level.
3. **Async safety** — uses `asyncio.Lock` per-path so concurrent coroutines in same event loop cannot interleave.
4. **Process safety (sync path)** — sync version uses `fcntl.flock(LOCK_EX)` for cross-process safety (e.g. hermes_bootstrap reading while backend writes). Best-effort: if flock unavailable (Windows), falls back to threading.Lock.
5. **Redaction is opt-in** — caller passes `redact(dict) -> dict`. If `None`, record passes through verbatim. Primitive does NOT know PII rules — caller decides. Example redact for prompt_log masks `name`/`phone`/`address` fields.
6. **Record is always dict-like** — non-dict passed = TypeError at boundary. No silent coerce.
7. **UTF-8, ensure_ascii=False** — Swedish chars survive round-trip.
8. **Newline handling** — record dict must not contain `"\n"` in any leaf string? No, we allow it; `json.dumps` escapes to `\n` inside the string, so line integrity is preserved.
9. **Encoding errors** — json.dumps of non-serialisable type raises TypeError up to caller; we do NOT swallow.
10. **Path creation** — parent dir is NOT auto-created. Caller is responsible. Avoids accidental scatter of log directories.

## Out of scope

- Log rotation (later).
- Remote sink (never — local files are contract).
- Structured schema validation (caller's concern).

## Migration plan

| Caller | Current primitive | Replace with |
|---|---|---|
| `error_logger.log_error` | `open(path, "a"); f.write(json)` | `append_jsonl(path, record)` (async context) or `append_jsonl_sync` |
| `prompt_log.record_prompt` | same | `append_jsonl(path, record, redact=_redact_pii)` |
| `issue_ledger._save` | `path.write_text(json.dumps(…))` | `write_json_atomic(path, data)` |
| `learning_journal.record` | `open; f.write` | `append_jsonl_sync(path, record)` |

Migrationerna görs EN åt gången efter matris grön. Gamla call-paths finns kvar tills migrerade moduler curl-verifierats.

## Invariant för downstream

Efter migration: `grep -rn "open(.*\.jsonl.*\"a\"" backend/` returnerar noll träffar. Om någon ny kod skriver direkt till jsonl = brott mot rule 12 (spec+matrix-first).
