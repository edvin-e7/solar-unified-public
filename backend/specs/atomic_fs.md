# Spec: services/atomic_fs.py

**Purpose.** Crash-safe file writes. Reader on disk always sees either the
previous content or the new content — never a partial. Solves
[docs/BUGS.md](../../docs/BUGS.md) Bug 5 (image writes), Bug 6 (prompt
auto-applicator), Bug 7 (scan history JSON).

The codebase already has `services.structured_log.write_json_atomic` for the
single-record JSON case. `atomic_fs` generalises the same tempfile + rename
pattern to:

- **Binary blobs** (e.g. satellite-tile JPEGs) — `write_bytes_atomic(path, data)`
- **UTF-8 text** (e.g. YAML-frontmatter prompts) — `write_text_atomic(path, text, encoding="utf-8")`
- **Arbitrary JSON** (delegates to `structured_log.write_json_atomic`) — re-exported as `write_json_atomic`

Single primitive, predictable behaviour, callable from anywhere in the backend.

## Public API

```python
def write_bytes_atomic(path: Path, data: bytes) -> None: ...
def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None: ...
def write_json_atomic(path: Path, data: Any) -> None: ...  # re-export
```

All raise `FileNotFoundError` if `path.parent` does not exist (consistent with
`structured_log`).

## Invariants

1. **Atomic-on-success.** When a call returns normally, the final `path` content
   equals exactly the `data` / `text` argument. No partial content visible.
2. **Atomic-on-failure.** If the write raises mid-call (disk full, kill -9,
   PermissionError, etc.), `path` either contains pre-call content or does not
   exist. Never partial. The tempfile MAY remain — see invariant 5.
3. **Replacement.** If `path` already exists, it is overwritten by `os.replace`
   (POSIX-atomic) or `path.replace` (cross-platform).
4. **No directory creation.** `path.parent` must exist; `FileNotFoundError` is
   raised otherwise. (Same contract as `structured_log.write_json_atomic`.)
5. **Tempfile naming.** The tempfile is `<path>.tmp`. If a previous run left a
   `.tmp` file, it is overwritten — not removed up-front (avoids a TOCTOU race).
6. **Concurrent writers.** Two concurrent calls on the same path are
   serialised via `_thread_lock_for(path)` (shared with `structured_log`).
   Cross-process: relies on `os.replace` atomicity. Last writer wins.
7. **Encoding.** `write_text_atomic` defaults to UTF-8. Other encodings
   accepted via `encoding=` kwarg.
8. **No fsync by default.** `os.replace` after `tempfile.write_*` is durable
   enough for our purpose (image cache, audit history, prompt versioning). We
   trade fsync's cost for throughput on the 6.3 GB Chromebook; if a power-loss
   scenario emerges, an `fsync=True` kwarg is the future extension point.

## Acceptance criterion (from BUGS.md Bugs 5–7)

- `kill -9` mid-scan: every `backend/data/images/*.jpg` is either complete (PIL-openable) or absent; no partial JPEGs and no leftover `.tmp` from in-flight scans.
- `kill -9` mid-auto-applicator: every prompt `*.md` has valid YAML frontmatter (or is the pre-write content).
- `kill -9` mid-save_history: every history JSON parses or is absent.

## Adversarial matrix

See `backend/specs/test_atomic_fs.py`. Covers:

| # | Case | What it stresses |
|---|---|---|
| A1 | Normal write to new path | Happy path |
| A2 | Normal write replacing existing file | `os.replace` semantics |
| A3 | Bytes round-trip including null/0xFF | Binary fidelity |
| A4 | Text round-trip with svenska Å/Ä/Ö + emoji | UTF-8 default |
| A5 | Text with explicit cp1252 encoding | Encoding kwarg honoured |
| A6 | Empty bytes | Edge case (degenerate but valid) |
| A7 | Empty text | Edge case |
| A8 | Large (10 MB) bytes | No truncation, no chunking bugs |
| A9 | Parent dir missing → FileNotFoundError | Contract enforced |
| A10 | Write fails mid-flight (mocked) → original preserved, tempfile state | Crash invariant |
| A11 | Concurrent same-path writers serialised | Thread-lock contract |
| A12 | Existing `.tmp` from prior run is overwritten | Invariant 5 |
| A13 | write_json_atomic re-export equals structured_log primitive | Compat |
| A14 | path with surrogate-pair filename (emoji 🌞) | Path encoding |
| A15 | Permission-denied on path → exception, original intact | Failure isolation |

## Non-goals

- Not a replacement for `services.structured_log.append_jsonl` (append-only
  with flock). atomic_fs is whole-file replacement only.
- Not a transaction across multiple files. Each call is independent.
- No fsync of parent directory (would harden against power loss at cost of
  ~5–20 ms per write — skipped as per invariant 8).

## Call sites this fix replaces

- `services/scanner.py:_save_image` — `path.write_bytes(data)` → `write_bytes_atomic(path, data)`
- `services/scanner.py:save_history` — `path.write_text(json.dumps(...))` → `write_json_atomic(path, list_of_results)`
- `executors/auto_applicator.py:_bump_prompt_version` — `path.write_text(new_content)` → `write_text_atomic(path, new_content)`
