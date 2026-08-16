#!/usr/bin/env python3
"""Every module in frontend/src must be reachable from something that runs it.

A module nothing imports still compiles, still type-checks, still passes
`pnpm build`. Reachability is the one property separating code that ships from
code that merely exists, and nothing else in `make verify` measures it — so this
frontend accumulated it silently: on 2026-08-16 a cross-repo sweep found six
modules here that no entry point reaches.

Three buckets, kept apart on purpose:

  orphan     no entry and no test reaches it. Dead.
  test-only  a test reaches it, the app never does. WORSE than dead, because it
             reports coverage — a green suite about code that ships to nobody.
             Counting tests as readers is precisely what hides this.
  parked     unreachable ON PURPOSE and said so in writing: the file sits in a
             legacy/ directory whose README.md names it. frontend/src/components/
             legacy/ holds three components salvaged from a predecessor app, each
             labelled "Not wired into the app yet" and each documented with the
             work it needs first. Sweeping them would be deleting deliberate
             salvage; ignoring the directory would make it a hiding place. The
             README requirement is what keeps it honest, and it is checked in
             both directions — a parked file the README omits fails, and a README
             entry with no file fails.

WHAT COUNTS AS AN ENTRY is the part that is easy to get wrong in the expensive
direction. The entries are every *.html in frontend/ plus the build config the
bundler executes — never a hardcoded module name. A sweep that guessed
`main.tsx` once read eight of a sibling repo's real window trees as dead code,
and a check that fails on working code gets deleted rather than obeyed.

Limit, stated rather than hidden: it follows static relative imports plus
`import("…")` with a literal path. A specifier built from a variable is invisible
to it, so "this check skips a file" is not proof the file is dead. A floor, not
a census.

Run standalone:  python3 scripts/frontend_reachability.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPT_SRC_RE = re.compile(r"""<script[^>]*\bsrc\s*=\s*['"]([^'"]+)['"]""", re.I)
IMPORT_RE = re.compile(
    r"""(?:\bfrom\s*|\bimport\s*\(\s*|\brequire\s*\(\s*|\bimport\s+)['"]([^'"]+)['"]"""
)
# `- **`Tour.tsx`** — …`: the README's own file list, not every backtick in it.
README_ENTRY_RE = re.compile(r"^\s*-\s+\*\*`([^`]+\.tsx?)`\*\*", re.M)
CONFIGS = ("vite.config.ts", "vite.config.js", "vitest.config.ts")
PARKED_DIRNAMES = {"legacy", "parked"}


def entry_points(frontend: Path, src: Path) -> list[Path]:
    """Entries as the BUNDLER sees them: every <script src> in every html."""
    found: list[Path] = []
    for html in sorted(frontend.glob("*.html")):
        for spec in SCRIPT_SRC_RE.findall(html.read_text(errors="ignore")):
            spec = spec.split("?")[0]
            cand = (frontend / spec.lstrip("/")) if spec.startswith("/") else (html.parent / spec)
            cand = cand.resolve()
            if cand.is_file() and str(cand).startswith(str(src)):
                found.append(cand)
    # Build config is an entry too — the bundler runs it, so a module imported
    # only from there is live.
    for name in CONFIGS:
        cfg = frontend / name
        if cfg.is_file():
            found.append(cfg.resolve())
    return sorted(set(found))


def _resolve(base: Path, spec: str) -> Path | None:
    if not spec.startswith("."):
        return None  # a real package, not our code
    p = (base.parent / spec).resolve()
    for cand in (p, Path(f"{p}.ts"), Path(f"{p}.tsx"), p / "index.ts", p / "index.tsx"):
        if cand.is_file():
            return cand
    return None


def reachable_from(starts: list[Path]) -> set[Path]:
    seen: set[Path] = set()
    stack = [s.resolve() for s in starts]
    while stack:
        f = stack.pop()
        if f in seen or not f.is_file() or f.suffix not in (".ts", ".tsx"):
            continue
        seen.add(f)
        for spec in IMPORT_RE.findall(f.read_text(errors="ignore")):
            r = _resolve(f, spec)
            if r and r not in seen:
                stack.append(r)
    return seen


def is_test(p: Path, src: Path) -> bool:
    return ".test." in p.name or ".spec." in p.name or "__tests__" in p.parts or f"{src}/test/" in str(p)


def parking_dir(p: Path) -> Path | None:
    """The parking directory documenting this file, or None.

    Both halves required: a directory segment named legacy/ or parked/, AND a
    README.md there that names the file. A folder called legacy is a habit; the
    README entry is the decision, and only a decision earns the exemption.
    """
    for i, part in enumerate(p.parts):
        if part.lower() in PARKED_DIRNAMES:
            readme = Path(*p.parts[: i + 1]) / "README.md"
            if readme.is_file() and p.name in readme.read_text(errors="ignore"):
                return readme.parent
    return None


def check(frontend: Path) -> str:
    src = (frontend / "src").resolve()
    if not src.is_dir():
        raise AssertionError(f"no frontend/src at {src}")

    allsrc = {
        p.resolve()
        for p in (*src.rglob("*.ts"), *src.rglob("*.tsx"))
        if not p.name.endswith(".d.ts") and "node_modules" not in p.parts
    }
    tests = {p for p in allsrc if is_test(p, src)}
    product = allsrc - tests

    entries = entry_points(frontend, src)
    assert entries, "no entry point found — every module would read as an orphan; that is a checker miss, not rot"

    from_app = reachable_from(entries)
    from_tests = reachable_from(sorted(tests))

    # Assert the graph is real BEFORE trusting its verdict. If the walk collapses,
    # everything looks orphaned and the list below becomes live code to delete.
    reached = product & from_app
    assert len(product) > 15, f"found only {len(product)} product modules — the tree walk broke"
    assert len(reached) > 15, f"walked only {len(reached)} modules — the entry points moved"

    unreached = product - from_app
    parked = {p for p in unreached if parking_dir(p)}
    rest = unreached - parked
    orphans = sorted(rest - from_tests)
    test_only = sorted(rest & from_tests)

    rel = lambda p: str(p.relative_to(src))  # noqa: E731
    assert not orphans, (
        "reachable from nothing at all — no entry, not even a test. Give them a reader, "
        "park them in a legacy/ directory with a README entry, or delete them: "
        + ", ".join(rel(p) for p in orphans)
    )
    assert not test_only, (
        "reachable ONLY from a test — green coverage of code the app never runs: "
        + ", ".join(rel(p) for p in test_only)
    )

    # Parking, checked in both directions so the prose cannot drift from the code.
    for d in sorted({parking_dir(p) for p in parked} | _parking_dirs(src)):
        on_disk = {f.name for f in (*d.glob("*.ts"), *d.glob("*.tsx"))}
        documented = set(README_ENTRY_RE.findall((d / "README.md").read_text(errors="ignore")))
        undocumented = sorted(on_disk - documented)
        assert not undocumented, (
            f"parked in {d.relative_to(src)}/ but absent from its README — say why it is kept "
            f"or delete it: {', '.join(undocumented)}"
        )
        missing = sorted(documented - on_disk)
        assert not missing, (
            f"named in {d.relative_to(src)}/README.md but not on disk — the doc outlived the "
            f"file: {', '.join(missing)}"
        )

    return f"{len(reached)}/{len(product)} modules reachable, {len(parked)} parked, 0 orphans"


def _parking_dirs(src: Path) -> set[Path]:
    """Parking directories that exist at all — so an EMPTY one still gets its
    README checked, and a directory whose README stopped naming its files cannot
    go quiet simply by having no parked file left in the bucket."""
    return {
        d
        for d in src.rglob("*")
        if d.is_dir() and d.name.lower() in PARKED_DIRNAMES and (d / "README.md").is_file()
    }


def main() -> int:
    frontend = Path(__file__).resolve().parent.parent / "frontend"
    try:
        print(f"[ok]   frontend-reachability — {check(frontend)}")
        return 0
    except AssertionError as e:
        print(f"[fail] frontend-reachability — {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
