"""Run every verification step end-to-end. Used by `make verify` and CI."""

from __future__ import annotations

import ast
import importlib
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[str, bool, str]] = []


def step(name: str, fn) -> None:
    try:
        detail = fn() or "ok"
        results.append((name, True, detail))
        print(f"  [ok]   {name} — {detail}")
    except (AssertionError, ImportError, OSError, SyntaxError, RuntimeError, ValueError) as e:
        # Verify is a meta-process: it must surface failures, not crash on
        # surprise exceptions. Catching the concrete classes the steps can
        # raise keeps us honest while still failing loudly on anything else.
        results.append((name, False, str(e)))
        print(f"  [fail] {name} — {type(e).__name__}: {e}")
        try:
            from error_logger import log_error

            log_error("verify-all", e, context={"step": name})
        except ImportError:
            # error_logger lives in backend/; if even that can't import,
            # the syntax/import-core step has already reported the cause.
            pass


def syntax_all() -> str:
    count = 0
    for py in ROOT.rglob("*.py"):
        if "__pycache__" in py.parts or "release" in py.parts:
            continue
        ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        count += 1
    return f"{count} files parse"


def import_core() -> str:
    importlib.import_module("prompts_loader")
    importlib.import_module("learning_journal")
    importlib.import_module("agents.coordinator")
    return "prompts_loader, learning_journal, agents.coordinator"


def prompts_load() -> str:
    from prompts_loader import list_prompts

    ps = list_prompts()
    assert len(ps) >= 5, "need ≥5 prompts"
    return f"{len(ps)} prompts"


def coordinator_boots() -> str:
    from agents.coordinator import Coordinator

    c = Coordinator()
    assert len(c.all) == 6, "expected 6 agents"
    return f"{len(c.all)} agents"


def frontend_reachable() -> str:
    """No module in frontend/src is left with nothing that runs it.

    Lives in scripts/frontend_reachability.py rather than here because it is a
    frontend concern with real logic; this file only decides that it runs. It
    raises AssertionError with the offending files, which step() reports as a
    failed check like any other.
    """
    repo = ROOT.parent
    sys.path.insert(0, str(repo / "scripts"))
    from frontend_reachability import check

    return check(repo / "frontend")


def journal_writable() -> str:
    from learning_journal import JOURNAL, record

    record("verify", "passed", "verify_all.py ran successfully")
    assert JOURNAL.exists(), "journal not created"
    return str(JOURNAL.relative_to(ROOT))


def main() -> int:
    print(f"==> Verifying {ROOT}")
    step("syntax", syntax_all)
    step("import-core", import_core)
    step("prompts", prompts_load)
    step("coordinator", coordinator_boots)
    step("frontend-reachability", frontend_reachable)
    step("journal", journal_writable)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
