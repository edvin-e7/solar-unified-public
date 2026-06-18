"""Adversarial matrix for services.structured_log.

Run: python3 backend/specs/test_structured_log.py
Or:  python3 -m pytest backend/specs/test_structured_log.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.structured_log import (
    append_jsonl,
    append_jsonl_sync,
    cleanup_stale_tmp,
    write_json_atomic,
)


def _tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="structlog_test_"))


# --- append_jsonl_sync ---

def test_append_jsonl_sync_single_line():
    d = _tmpdir()
    p = d / "log.jsonl"
    append_jsonl_sync(p, {"a": 1})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"a": 1}


def test_append_jsonl_sync_multi_line():
    d = _tmpdir()
    p = d / "log.jsonl"
    for i in range(5):
        append_jsonl_sync(p, {"i": i})
    lines = p.read_text(encoding="utf-8").splitlines()
    assert [json.loads(l)["i"] for l in lines] == [0, 1, 2, 3, 4]


def test_append_jsonl_sync_swedish_chars_roundtrip():
    d = _tmpdir()
    p = d / "log.jsonl"
    append_jsonl_sync(p, {"name": "Åsa Ängström", "city": "Göteborg"})
    line = p.read_text(encoding="utf-8").splitlines()[0]
    got = json.loads(line)
    assert got["name"] == "Åsa Ängström"
    assert got["city"] == "Göteborg"
    # Ensure ensure_ascii=False was honoured (no \u escapes):
    assert "Åsa" in line


def test_append_jsonl_sync_redact_hook_applied():
    d = _tmpdir()
    p = d / "log.jsonl"

    def redact(r: dict) -> dict:
        r = dict(r)
        if "phone" in r:
            r["phone"] = "<redacted>"
        return r

    append_jsonl_sync(p, {"name": "Edvin", "phone": "070-1234567"}, redact=redact)
    got = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert got["phone"] == "<redacted>"
    assert got["name"] == "Edvin"


def test_append_jsonl_sync_concurrent_threads_no_corruption():
    """N threads append K records each; total lines = N*K and all parseable."""
    d = _tmpdir()
    p = d / "log.jsonl"
    n_threads = 8
    per = 25

    def worker(tid: int) -> None:
        for i in range(per):
            append_jsonl_sync(p, {"tid": tid, "i": i})

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n_threads * per
    # Every line parseable (not interleaved):
    for line in lines:
        json.loads(line)


def test_append_jsonl_sync_rejects_non_dict():
    d = _tmpdir()
    p = d / "log.jsonl"
    try:
        append_jsonl_sync(p, "not a dict")  # type: ignore[arg-type]
        raise AssertionError("should have raised TypeError")
    except TypeError:
        pass  # invariant-ok: PY-SILENT-EXC — test asserts expected TypeError


def test_append_jsonl_sync_does_not_create_parent_dir():
    d = _tmpdir()
    nonexistent = d / "does-not-exist" / "log.jsonl"
    try:
        append_jsonl_sync(nonexistent, {"a": 1})
        raise AssertionError("should have raised FileNotFoundError")
    except FileNotFoundError:
        pass  # invariant-ok: PY-SILENT-EXC — test asserts expected FileNotFoundError


# --- append_jsonl (async) ---

def test_append_jsonl_async_single_line():
    d = _tmpdir()
    p = d / "log.jsonl"

    async def run():
        await append_jsonl(p, {"a": 1})

    asyncio.run(run())
    got = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert got == {"a": 1}


def test_append_jsonl_async_concurrent_coroutines_no_corruption():
    d = _tmpdir()
    p = d / "log.jsonl"

    async def run():
        await asyncio.gather(*[append_jsonl(p, {"i": i}) for i in range(50)])

    asyncio.run(run())
    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 50
    ids = sorted(json.loads(l)["i"] for l in lines)
    assert ids == list(range(50))


def test_append_jsonl_async_redact_hook_applied():
    d = _tmpdir()
    p = d / "log.jsonl"

    def redact(r: dict) -> dict:
        return {**r, "phone": "<redacted>"}

    async def run():
        await append_jsonl(p, {"phone": "070-xxx"}, redact=redact)

    asyncio.run(run())
    got = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert got["phone"] == "<redacted>"


# --- write_json_atomic ---

def test_write_json_atomic_produces_valid_json():
    d = _tmpdir()
    p = d / "state.json"
    write_json_atomic(p, {"version": 1, "issues": {}})
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got == {"version": 1, "issues": {}}


def test_write_json_atomic_overwrite_is_atomic_rename():
    d = _tmpdir()
    p = d / "state.json"
    write_json_atomic(p, {"v": 1})
    write_json_atomic(p, {"v": 2})
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": 2}
    # No stale tmp left behind after successful write:
    assert not (p.with_suffix(".json.tmp").exists())


def test_write_json_atomic_swedish_chars_roundtrip():
    d = _tmpdir()
    p = d / "state.json"
    write_json_atomic(p, {"city": "Göteborg"})
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got["city"] == "Göteborg"


def test_write_json_atomic_redact_applied_for_dict():
    d = _tmpdir()
    p = d / "state.json"

    def redact(r: dict) -> dict:
        return {k: "<redacted>" if k == "phone" else v for k, v in r.items()}

    write_json_atomic(p, {"phone": "070", "name": "Edvin"}, redact=redact)
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got == {"phone": "<redacted>", "name": "Edvin"}


def test_write_json_atomic_redact_ignored_for_non_dict_root():
    """If root is a list, we don't apply a dict-redact — list passes through."""
    d = _tmpdir()
    p = d / "state.json"
    write_json_atomic(p, [1, 2, 3], redact=lambda r: r)
    got = json.loads(p.read_text(encoding="utf-8"))
    assert got == [1, 2, 3]


# --- cleanup_stale_tmp ---

def test_cleanup_stale_tmp_removes_sibling():
    d = _tmpdir()
    p = d / "state.json"
    (p.with_suffix(".json.tmp")).write_text("{}")
    cleanup_stale_tmp(p)
    assert not (p.with_suffix(".json.tmp")).exists()


def test_cleanup_stale_tmp_no_op_when_missing():
    d = _tmpdir()
    p = d / "state.json"
    # Must not crash
    cleanup_stale_tmp(p)


# --- determinism / idempotence guarantees ---

def test_append_then_read_is_deterministic_order():
    d = _tmpdir()
    p = d / "log.jsonl"
    for i in range(10):
        append_jsonl_sync(p, {"i": i})
    got = [json.loads(l)["i"] for l in p.read_text(encoding="utf-8").splitlines()]
    assert got == list(range(10))


def test_write_atomic_under_crash_leaves_old_file_intact():
    """Simulate mid-write crash: tmp file exists but final rename did not happen.
    The original file should still be readable and intact."""
    d = _tmpdir()
    p = d / "state.json"
    write_json_atomic(p, {"v": "original"})
    # Manually create a stale tmp (simulating crash during write)
    p.with_suffix(".json.tmp").write_text("{'half-written': ")  # corrupt json
    # Reader still sees original
    assert json.loads(p.read_text(encoding="utf-8")) == {"v": "original"}
    # Cleanup removes stale tmp
    cleanup_stale_tmp(p)
    assert not (p.with_suffix(".json.tmp")).exists()


def _run_all():
    import traceback

    g = globals()
    names = sorted(n for n in g if n.startswith("test_"))
    passed = 0
    failed: list[tuple[str, str]] = []
    for name in names:
        try:
            g[name]()
            passed += 1
            print(f"  [PASS] {name}")
        except Exception as exc:
            failed.append((name, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
            print(f"  [FAIL] {name}: {exc}")
    print(f"\n{passed}/{len(names)} passed, {len(failed)} failed")
    if failed:
        print("\n--- failures ---")
        for name, tb in failed:
            print(f"\n[{name}]\n{tb}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
