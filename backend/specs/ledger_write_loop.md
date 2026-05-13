---
name: ledger_write_loop
version: 1
audience: claude
description: Contract for how the autonomous improvement cycle writes to issue_ledger so the anti-brainrot filter has a corpus to match against. Infra failures MUST NOT pollute the ledger.
---

# Spec — orchestrator ↔ issue_ledger write contract

## Why

`issue_ledger.similar_attempts` is read from `improvement_generator._filter_already_tried` to block paraphrases of prior rejected hypotheses. The filter is useless unless the ledger grows from real cycles. Before this spec, the orchestrator ran verify + apply but never called `open_issue` / `log_attempt` / `resolve_issue` — so the ledger only contained seeded entries.

Equally critical: a transient Gemini 429 in cove_verifier currently falls back to mock answers and returns `verified=False`. If we write that to the ledger as `rejected_by_cove`, next cycle will filter the SAME improvement as "already tried" despite never having really tried it — ledger poisoning by infra noise.

## Public API (orchestrator view)

For each `(pattern, improvement)` pair that survives the filter:

```python
key = issue_ledger.open_issue(
    error_type=pattern["name"],            # e.g. "low_detection_confidence"
    target=improvement["target"],
    title=improvement["enhancement"][:80],
    tags=[improvement.get("type", "unknown")],
    evidence={"pattern_frequency": pattern.get("frequency")},
)

cove = await collective_verify.verify_improvement(improvement)

if cove.get("llm_errors"):
    # Infra failure — journal it but DO NOT write to ledger.
    # Ledger write would create a false "we tried this and it failed" signal.
    journaler.journal_infra_degradation(pattern=..., errors=cove["llm_errors"])
    continue

if not cove["verified"]:
    log_attempt(
        key=key,
        hypothesis=improvement["enhancement"],
        change_summary=improvement["rationale"],
        outcome="rejected_by_cove",
        evidence={"confidence": cove["confidence"], "reasoning": cove["reasoning"]},
    )
    continue

apply_result = auto_apply.apply_improvement(improvement, cove)

if apply_result["applied"]:
    log_attempt(
        key=key,
        hypothesis=improvement["enhancement"],
        change_summary=improvement["rationale"],
        outcome="success",
        evidence={"commit": apply_result.get("commit"), "confidence": cove["confidence"]},
    )
    # log_attempt(success) already resolves the issue, no explicit resolve call needed.
else:
    log_attempt(
        key=key,
        hypothesis=improvement["enhancement"],
        change_summary=improvement["rationale"],
        outcome="failed",
        evidence={"apply_error": apply_result.get("reason"), "confidence": cove["confidence"]},
    )
```

## Invariants

1. **Infra failure must not write the ledger** — if `cove["llm_errors"]` is truthy, no `log_attempt` call is made for that improvement. The filter never sees the attempt → next cycle retries cleanly once quota returns.
2. **Idempotent issue keys** — same `(pattern.name, target)` pair → same 12-char SHA1 key across cycles. `open_issue` increments `occurrences` + updates `last_seen`; it never creates a duplicate.
3. **Every recorded attempt has a hypothesis** — the `enhancement` text is the hypothesis the filter later matches against via token-similarity. Empty hypothesis = wasted ledger entry, blocked at orchestrator level.
4. **Outcome taxonomy is closed** — `success | failed | rejected_by_cove | rejected_by_design | blocked | partial`. Infra failures get `skipped-infra` journal entry, never a ledger outcome.
5. **Write failures must not crash the cycle** — `log_attempt` or `open_issue` raising must be caught + `log_error`'d. The cycle continues with the next improvement.
6. **Read-then-write round-trip**: if a cycle logs an attempt with outcome ∈ {failed, rejected_by_cove, rejected_by_design}, the NEXT cycle with the same (pattern, improvement) MUST see that attempt surface in `similar_attempts` and be blocked.
7. **Success resolves** — `log_attempt(outcome="success")` sets `issue["status"]="resolved"` and populates `issue["resolution"]`. The improvement_generator filter default (`include_outcomes` excludes successes) ensures resolved issues don't block future fresh attempts of the same idea if new data justifies it.
8. **Tags carry improvement type** — `["prompt_refinement" | "logic_fix" | "config_change"]`. Dashboards can slice by type.

## `cove_verifier.verify_improvement` contract addition

Return dict gains one field:

- `llm_errors: list[str]` — populated when a sub-call fell back to rule-based/mock output. Values:
  - `"questions_fallback"` — `generate_verification_questions_llm` returned `[]` (Gemini errored or unparseable)
  - `"answers_fallback"` — `answer_questions_llm` returned mock neutrals (Gemini errored)

Empty list = both LLM steps succeeded → result is trustworthy. Non-empty = at least one step degraded → downstream must decide whether to trust.

This requires minimal change: the existing try/excepts already know when fallback fires. We pipe that signal up via return value instead of burying it in error_logger only.

## Test matrix — `test_orchestrator_ledger_write.py`

Adversarial cases:

1. **First run, no prior** — open_issue creates, log_attempt(rejected_by_cove) appends. Second run of SAME (pattern, improvement) → filter blocks.
2. **First run, infra failure** — `cove["llm_errors"] = ["answers_fallback"]` → NO ledger write. Next run without infra failure proceeds normally (filter does not block).
3. **Success path** — verified=True + applied=True → log_attempt(success) → issue.status=resolved.
4. **Apply failure** — verified=True + applied=False → log_attempt(failed) with apply_error in evidence.
5. **Idempotent issue key** — two cycles, same pattern+target → same key → occurrences=2, attempts list grows, no duplicate issue.
6. **Ledger corruption resilience** — mock `log_attempt` to raise → orchestrator logs via error_logger + continues. Cycle still returns a sensible result dict.
7. **Multiple improvements same cycle** — 3 patterns → 3 issue keys → 3 independent attempt traces.
8. **Empty hypothesis guarded** — improvement with empty `enhancement` never calls log_attempt.

## Non-goals

- Automatic `reopen_issue` on recurrence (deferred — needs pattern-frequency-trend analysis).
- Ledger-backed "confidence decay" over time (deferred).
- Cross-pattern issue linking (single (pattern, target) key is authoritative).
