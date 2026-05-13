"""Self-improving loop layer.

After each verify_v2 run:
  1. Generate next-iteration prompt from current verifier state (rule-based ranker)
  2. CoVe-verify the prompt — 5 Q&A against confidence gate before next loop uses it
  3. Distill the previous-iteration lesson — did the last prompt's predicted outcome
     match the actual delta in stage state? Save to memory if non-obvious.
  4. Append to verify/iterations.jsonl (history of prompts + outcomes for ReasoningBank).

Per Edvin's directive 2026-04-27: every loop should evaluate + improve the prompt
before continuing — not just execute the same plan blindly.

Run via:  python backend/scripts/next_loop.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

VERIFY_DIR = ROOT / "verify"
ITERATIONS_LOG = VERIFY_DIR / "iterations.jsonl"
NEXT_PROMPT = VERIFY_DIR / "next_prompt.md"


@dataclass
class StageState:
    name: str
    passed: bool
    bug_count: int
    issue_key: str | None


@dataclass
class IterationRecord:
    ts: str
    prompt: str
    cove_verified: bool
    cove_confidence: float
    cove_q_and_a: list[dict]
    predicted_next_state: dict[str, int]  # stage_name -> predicted bug_count after this iteration
    actual_next_state: dict[str, int] | None = None  # filled by next iteration
    lesson: str | None = None


PRIORITY_ORDER = [
    # (stage_name, why-it's-blocking-felfri, fix-leverage)
    ("opt_drift", "production app serves stale code → user-flow can fail silently", 10),
    ("bare_except_audit", "every site is a potential silent-fail per CLAUDE.md rule 6", 9),
    ("silent_return_audit", "empty-return-in-except = silent-fail, masks bugs in journal", 9),
    ("prd_parity", "PRD lying about [x] erodes trust + obscures real status", 7),
    ("spec_coverage", "missing spec = no adversarial matrix = future regression", 6),
    ("idempotency_canary", "non-idempotent batch → re-run breaks data, blocks rule 9", 8),
    ("golden_path_browser", "actual end-user flow — felfri criterion gate", 10),
]


def load_last_iteration() -> IterationRecord | None:
    if not ITERATIONS_LOG.exists():
        return None
    lines = [ln for ln in ITERATIONS_LOG.read_text().splitlines() if ln.strip()]
    if not lines:
        return None
    return IterationRecord(**json.loads(lines[-1]))


def load_current_state() -> list[StageState]:
    """Reads verify_v2 output JSON from stdin or runs verify_v2 fresh."""
    import subprocess
    venv_py = BACKEND / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    proc = subprocess.run(
        [py, "backend/scripts/verify_v2.py"],
        capture_output=True, text=True, cwd=ROOT,
    )
    # Parse the trailing JSON baseline block
    out = proc.stdout
    if "--- baseline ---" not in out:
        raise RuntimeError(f"verify_v2.py did not emit baseline block:\n{out[-500:]}")
    json_str = out.split("--- baseline ---", 1)[1].strip()
    raw = json.loads(json_str)
    return [StageState(name=r["name"], passed=r["passed"],
                       bug_count=r.get("bug_count", 0), issue_key=r.get("issue_key"))
            for r in raw]


def rank_stages(states: list[StageState]) -> list[tuple[StageState, int]]:
    """Sort failing stages by (priority * bug_count) — biggest leverage first."""
    by_name = {n: lev for n, _, lev in PRIORITY_ORDER}
    failing = [s for s in states if not s.passed]
    return sorted(
        ((s, by_name.get(s.name, 5) * max(s.bug_count, 1)) for s in failing),
        key=lambda x: -x[1],
    )


def generate_prompt(states: list[StageState]) -> tuple[str, dict[str, int]]:
    """Build the next-iteration prompt + predicted state after this iteration."""
    ranked = rank_stages(states)
    if not ranked:
        return "All verifier stages green. Move to golden-path browser stage (Phase 2a) — felfri gate.", {}

    top = ranked[0][0]
    others = [r[0] for r in ranked[1:]]

    # Predict: top stage drops to 0 after this iteration; others unchanged
    predicted = {s.name: s.bug_count for s in states}
    predicted[top.name] = 0

    why_lookup = {n: why for n, why, _ in PRIORITY_ORDER}
    prompt_lines = [
        f"# Next iteration prompt (generated {datetime.now(UTC).isoformat()})",
        "",
        f"## Top priority: drive `{top.name}` from {top.bug_count} → 0",
        "",
        f"**Why blocking felfri:** {why_lookup.get(top.name, '(no rationale)')}",
        f"**Ledger entry:** `{top.issue_key}` (auto-opened by verify_v2)",
        "",
        "## Approach",
    ]
    if top.name == "bare_except_audit":
        prompt_lines += [
            "1. Run `ruff check --select BLE001 backend/` to get full site list",
            "2. For each production site: read context → identify actual exception types → replace `except Exception` with `except (Type1, Type2) as e` + `error_logger.log_error(phase, e, context={...})` per CLAUDE.md rule 6",
            "3. For legitimate fail-soft (per-item batch loops): keep `except Exception` BUT add `# noqa: BLE001 -- <reason>` and ensure `error_logger.log_error` is called",
            "4. Re-run verify_v2.py — bare_except_audit stage must pass",
            "5. One commit per file or per logical group",
        ]
    elif top.name == "prd_parity":
        prompt_lines += [
            "1. Parse `PRD.md` for all `- [x]` claims",
            "2. For each: find evidence file/test that backs it",
            "3. If evidence missing: revert to `- [ ]` (PRD must not lie)",
            "4. Re-run verify_v2.py — prd_parity stage must pass",
            "5. Commit PRD update with rationale per missing evidence",
        ]
    elif top.name == "spec_coverage":
        prompt_lines += [
            "1. Get list of 27 missing modules from verify_v2 evidence",
            "2. Prioritize: api/* (user-facing) → services/* → agents/* → executors/*",
            "3. For each: write `backend/specs/<module>.md` (numbered invariants) + `backend/specs/test_<module>.py` (adversarial matrix)",
            "4. Per CLAUDE.md rule 12: matrix must include explicit stress cases (concurrency, crash-replay, paraphrase, stopwords, Unicode, empty, boundary, adversarial)",
            "5. Implement until matrix green",
        ]
    else:
        prompt_lines += [
            f"1. Inspect `backend/scripts/verify_v2.py::{top.name}` for the exact failure pattern",
            "2. Read ledger entry attempts for prior approaches (`issue_ledger.find_issue`)",
            "3. Apply fix per CLAUDE.md rule 4 (deep analyze → plan → implement → verify, no shortcuts)",
            "4. Re-run verify_v2.py — stage must pass",
        ]

    prompt_lines += [
        "",
        "## Predicted state after this iteration",
        f"```json\n{json.dumps(predicted, indent=2)}\n```",
        "",
        "## Other failing stages (deferred to subsequent iterations)",
    ]
    for s in others:
        prompt_lines.append(f"- `{s.name}` ({s.bug_count} bugs) — ledger {s.issue_key}")
    prompt_lines += [
        "",
        "## Self-eval gate (CoVe — 5 Q&A) before executing this prompt:",
        "1. Is this the highest-leverage failure right now? (priority × bug_count)",
        "2. Does the approach respect CLAUDE.md rule 4 (no shortcuts)?",
        "3. Will completing this unblock subsequent stages, or is it independent?",
        "4. Are there prior ledger attempts on this stage that already failed?",
        "5. Does the predicted state assume too much (e.g. dropping to 0 in one iteration when realistic is partial)?",
        "",
        "If any answer is uncertain, lower confidence and revise prompt before next loop executes.",
    ]
    return "\n".join(prompt_lines), predicted


def cove_verify_prompt(prompt: str) -> dict:
    """Lightweight self-verification — rule-based for now, LLM-upgradeable.

    Returns confidence in [0, 1]. Threshold 0.75 per CoVe gate.
    """
    score = 1.0
    qa: list[dict] = []

    # Q1: Does the prompt name a concrete top action?
    has_top = "Top priority:" in prompt and "→ 0" in prompt
    qa.append({"q": "concrete top action?", "a": has_top, "weight": 0.2})
    score -= 0 if has_top else 0.2

    # Q2: Does it cite the ledger entry?
    has_ledger = "Ledger entry:" in prompt
    qa.append({"q": "ledger entry cited?", "a": has_ledger, "weight": 0.15})
    score -= 0 if has_ledger else 0.15

    # Q3: Does it list a numbered approach (steps)?
    has_steps = "1." in prompt and "2." in prompt
    qa.append({"q": "numbered approach?", "a": has_steps, "weight": 0.15})
    score -= 0 if has_steps else 0.15

    # Q4: Does it predict next state?
    has_prediction = "Predicted state" in prompt
    qa.append({"q": "predicted next state?", "a": has_prediction, "weight": 0.2})
    score -= 0 if has_prediction else 0.2

    # Q5: Does it reference CLAUDE.md rules (not generic)?
    has_rules = "CLAUDE.md" in prompt
    qa.append({"q": "references project rules?", "a": has_rules, "weight": 0.3})
    score -= 0 if has_rules else 0.3

    return {"verified": score >= 0.75, "confidence": round(score, 3), "q_and_a": qa}


def distill_lesson(prev: IterationRecord, current_states: list[StageState]) -> str | None:
    """Compare predicted vs actual. Surface lesson if they diverge."""
    if not prev or not prev.predicted_next_state:
        return None
    actual = {s.name: s.bug_count for s in current_states}
    diffs = []
    for stage, predicted_count in prev.predicted_next_state.items():
        actual_count = actual.get(stage, "?")
        if actual_count != predicted_count:
            diffs.append(f"{stage}: predicted={predicted_count}, actual={actual_count}")
    if not diffs:
        return "Prediction matched reality on all stages — confidence calibrated."
    return f"Prediction-vs-actual divergence: {'; '.join(diffs)}"


def main() -> int:
    VERIFY_DIR.mkdir(exist_ok=True)
    states = load_current_state()
    prev = load_last_iteration()

    prompt, predicted = generate_prompt(states)
    cove = cove_verify_prompt(prompt)
    lesson = distill_lesson(prev, states) if prev else None

    record = IterationRecord(
        ts=datetime.now(UTC).isoformat(),
        prompt=prompt,
        cove_verified=cove["verified"],
        cove_confidence=cove["confidence"],
        cove_q_and_a=cove["q_and_a"],
        predicted_next_state=predicted,
        lesson=lesson,
    )

    # Backfill prev iteration's actual_next_state if we have one
    if prev:
        prev.actual_next_state = {s.name: s.bug_count for s in states}
        # Rewrite last line of jsonl with backfilled actuals
        if ITERATIONS_LOG.exists():
            lines = ITERATIONS_LOG.read_text().splitlines()
            if lines:
                lines[-1] = json.dumps(asdict(prev), default=str)
                ITERATIONS_LOG.write_text("\n".join(lines) + "\n")

    with ITERATIONS_LOG.open("a") as f:
        f.write(json.dumps(asdict(record), default=str) + "\n")

    NEXT_PROMPT.write_text(prompt + f"\n\n## CoVe self-eval\n```json\n{json.dumps(cove, indent=2)}\n```\n"
                                   + (f"\n## Lesson from previous iteration\n{lesson}\n" if lesson else ""))

    print("==> next_loop")
    print(f"  CoVe verified: {cove['verified']} (confidence {cove['confidence']})")
    if lesson:
        print(f"  Lesson: {lesson}")
    print(f"  Prompt → {NEXT_PROMPT.relative_to(ROOT)}")
    print(f"  History → {ITERATIONS_LOG.relative_to(ROOT)} ({sum(1 for _ in ITERATIONS_LOG.open()) if ITERATIONS_LOG.exists() else 0} iterations)")
    return 0 if cove["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
