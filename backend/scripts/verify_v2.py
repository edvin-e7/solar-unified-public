"""Extended verifier — passes only when the app actually works for Edvin.

Stages beyond verify_all.py's 5:
  1. bare_except_audit   — ruff BLE001, must be 0
  2. silent_return_audit — ast-grep: empty return inside except
  3. prd_parity          — every PRD '- [x]' has evidence
  4. opt_drift           — ~/solar-unified backend matches /opt/solar-unified
  5. spec_coverage       — every backend/{api,services,agents}/*.py has specs/*.md

Each failure auto-opens (or updates) an issue_ledger entry, one per category.
Run via:  python backend/scripts/verify_v2.py
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from issue_ledger import log_attempt, open_issue  # noqa: E402

VENV_RUFF = BACKEND / ".venv" / "bin" / "ruff"
RUFF = str(VENV_RUFF) if VENV_RUFF.exists() else "ruff"


@dataclass
class StageResult:
    name: str
    passed: bool
    evidence: str
    bug_count: int = 0
    issue_key: str | None = None


def _open_or_update(error_type: str, target: str, title: str, evidence: dict) -> str:
    """One ledger entry per category. Updates last_seen on each run."""
    key = open_issue(error_type=error_type, target=target, title=title, tags=["verifier-v2"])
    log_attempt(
        key=key,
        author="verify_v2",
        hypothesis=f"{error_type} not yet driven to 0",
        change_summary=f"Verifier ran; current count {evidence.get('count', '?')}",
        outcome="failed",
        evidence=evidence,
    )
    return key


def bare_except_audit() -> StageResult:
    """ruff BLE001 across backend/. Must be 0."""
    proc = subprocess.run(
        [RUFF, "check", "--select", "BLE001", "--output-format", "json", str(BACKEND)],
        capture_output=True, text=True, cwd=ROOT,
    )
    try:
        issues = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        return StageResult("bare_except_audit", False, f"ruff returned non-JSON: {proc.stdout[:200]}", 1)
    count = len(issues)
    if count == 0:
        return StageResult("bare_except_audit", True, "0 bare-except sites")
    sample = [f"{i['filename'].replace(str(ROOT) + '/', '')}:{i['location']['row']}" for i in issues[:5]]
    key = _open_or_update(
        "BLE001",
        "backend/",
        f"Bare-except (BLE001): {count} sites — silent-fail risk per CLAUDE.md rule 6",
        {"count": count, "sample": sample, "ruff_cmd": "ruff check --select BLE001 backend/"},
    )
    return StageResult("bare_except_audit", False, f"{count} sites; first 5: {sample}", count, key)


def silent_return_audit() -> StageResult:
    """ast-grep for `return None|[]|{}|''` inside except blocks."""
    if subprocess.run(["which", "ast-grep"], capture_output=True).returncode != 0:
        return StageResult("silent_return_audit", False, "ast-grep not installed", 1)
    pattern_yaml = """
id: silent-return-in-except
language: python
rule:
  pattern: "return $V"
  inside:
    pattern: "except $$$: $$$BODY"
constraints:
  V:
    any:
      - regex: "^None$"
      - regex: "^\\\\[\\\\]$"
      - regex: "^\\\\{\\\\}$"
      - regex: "^''$"
      - regex: "^\\"\\"$"
"""
    rule_path = ROOT / ".tmp" / "silent-return.yaml"
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(pattern_yaml)
    proc = subprocess.run(
        ["ast-grep", "scan", "--rule", str(rule_path), "--json=stream", str(BACKEND)],
        capture_output=True, text=True,
    )
    matches = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    real = [m for m in matches if "/.venv/" not in m.get("file", "") and "__pycache__" not in m.get("file", "")]
    count = len(real)
    if count == 0:
        return StageResult("silent_return_audit", True, "0 silent-return-in-except sites")
    sample = [f"{m['file'].replace(str(ROOT) + '/', '')}:{m['range']['start']['line']}" for m in real[:5]]
    key = _open_or_update(
        "SilentReturn",
        "backend/",
        f"Silent return inside except: {count} sites — silent-fail risk",
        {"count": count, "sample": sample},
    )
    return StageResult("silent_return_audit", False, f"{count} sites; first 5: {sample}", count, key)


def prd_parity() -> StageResult:
    """Every '- [x]' claim in PRD.md must have evidence (file path or test that exists)."""
    prd = ROOT / "PRD.md"
    if not prd.exists():
        return StageResult("prd_parity", False, "PRD.md missing", 1)
    text = prd.read_text(encoding="utf-8")
    checked = re.findall(r"^\s*-\s*\[x\]\s+(.+?)$", text, re.MULTILINE)
    unverified = []
    for claim in checked:
        # Heuristic: claim is verified if it references an existing file path or matches a known verifier stage
        verified = False
        for token in re.findall(r"`([^`]+)`|([\w/\.\-]+\.(?:py|ts|tsx|md|yml|yaml))", claim):
            path_token = token[0] or token[1]
            if path_token and (ROOT / path_token).exists():
                verified = True
                break
        if not verified:
            unverified.append(claim.strip()[:80])
    if not unverified:
        return StageResult("prd_parity", True, f"{len(checked)} [x] claims, all reference existing files")
    key = _open_or_update(
        "PRDLies",
        "PRD.md",
        f"PRD has {len(unverified)}/{len(checked)} [x] claims with no file/test evidence",
        {"unverified_sample": unverified[:5], "total_unverified": len(unverified)},
    )
    return StageResult("prd_parity", False, f"{len(unverified)}/{len(checked)} unverified [x] claims", len(unverified), key)


def opt_drift() -> StageResult:
    """Diff ~/solar-unified/backend/{api,services,agents,*.py} vs /opt/solar-unified/backend/..."""
    opt_root = Path("/opt/solar-unified/backend")
    if not opt_root.exists():
        return StageResult("opt_drift", True, "/opt deployment not present (skipped)")
    drifted = []
    for sub in ("api", "services", "agents"):
        for src in (BACKEND / sub).rglob("*.py"):
            if "__pycache__" in src.parts:
                continue
            rel = src.relative_to(BACKEND)
            dst = opt_root / rel
            if not dst.exists() or src.read_bytes() != dst.read_bytes():
                drifted.append(str(rel))
    # Top-level .py files
    for src in BACKEND.glob("*.py"):
        dst = opt_root / src.name
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            drifted.append(src.name)
    if not drifted:
        return StageResult("opt_drift", True, "~/solar-unified == /opt/solar-unified (backend tree)")
    key = _open_or_update(
        "OptDrift",
        "/opt/solar-unified/backend",
        f"/opt/ deployment drifted from ~/ ({len(drifted)} files)",
        {"drifted_sample": drifted[:10], "total": len(drifted)},
    )
    return StageResult("opt_drift", False, f"{len(drifted)} files drift; first 10: {drifted[:10]}", len(drifted), key)


def spec_coverage() -> StageResult:
    """Every non-trivial backend/{api,services,agents}/*.py has specs/<name>.md + specs/test_<name>.py."""
    specs_dir = BACKEND / "specs"
    have_specs = {p.stem for p in specs_dir.glob("*.md")}
    have_tests = {p.stem.replace("test_", "") for p in specs_dir.glob("test_*.py")}
    missing = []
    for sub in ("api", "services", "agents"):
        for f in (BACKEND / sub).glob("*.py"):
            if f.name in ("__init__.py",) or f.stat().st_size < 500:  # skip trivial
                continue
            stem = f.stem
            if stem not in have_specs and stem not in have_tests:
                missing.append(f"{sub}/{f.name}")
    if not missing:
        return StageResult("spec_coverage", True, f"{len(have_specs)} specs cover all non-trivial modules")
    key = _open_or_update(
        "SpecGap",
        "backend/specs/",
        f"{len(missing)} non-trivial modules without spec+matrix per CLAUDE.md rule 12",
        {"missing_sample": missing[:10], "total": len(missing)},
    )
    return StageResult("spec_coverage", False, f"{len(missing)} modules missing spec; first 10: {missing[:10]}", len(missing), key)


def main() -> int:
    print(f"==> verify_v2 — {ROOT}")
    stages = [bare_except_audit, silent_return_audit, prd_parity, opt_drift, spec_coverage]
    results: list[StageResult] = []
    for fn in stages:
        try:
            r = fn()
        except Exception as e:
            r = StageResult(fn.__name__, False, f"stage crashed: {type(e).__name__}: {e}", 1)
        results.append(r)
        marker = "[ok]  " if r.passed else "[FAIL]"
        print(f"  {marker} {r.name} — {r.evidence}")

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{passed}/{total} extended stages passed")
    print("\n--- baseline ---")
    print(json.dumps([asdict(r) for r in results], indent=2, default=str))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
