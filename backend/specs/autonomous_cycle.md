# `scripts/run_autonomous_cycle.py` — invariants

The autonomous learning cycle reads the journal, generates improvement
suggestions, votes via CoVe, and journals the outcome. It is the gate
the Opus verifier rejected 18 consecutive times before Fas 1. The four
meta-bugs the verifier documented in `prompts/learned/summary.md` are
the inverse of the invariants here — if any of these break we are back
in the rubber-stamp loop.

## Invariants

1. **Verify-count uses exact match against canonical phases.** Only
   `verify` and `verify-all` count. `cove-verify`, `cove-verify-opus`,
   `agent-verify-*`, `collective-verify` MUST NOT contribute. This
   replaces the substring bug `'verify' in str(k)` that let the
   verifier's own entries self-arm S2 forever.
2. **`cove_vote()` is content-analytical, not risk-table.** Voting score
   comes from five binary signals: hot-file overlap, antipattern citation,
   substantive rationale (>=50 chars), non-trivial template (>=200 chars),
   and specific (non-boilerplate) title. Risk only sets the *threshold*
   the score must clear: low=3, medium=4, high=5. No suggestion gets
   approval just for being labeled low-risk.
3. **`already_exists=True` is an immediate reject.** Idempotent guard so
   the cycle does not approve writing a file that is already on disk.
   Returns 0/5 votes regardless of content score.
4. **`outcome='no_op'` (not `'passed'`) when no suggestion was applied.**
   Stops the +0.2%/cycle inflation of `success_rate` via self-telemetry.
   `passed` is reserved for cycles that actually wrote at least one file
   (full mode) or had at least one CoVe-approved suggestion (learning-only).
5. **`success_rate` excludes no-op autonomous-cycle entries.** `analyze()`
   does not count `phase='autonomous-cycle'` rows whose
   `metadata.suggestions_applied == 0` toward the numerator. Combined
   with invariant 4 this closes the inflation loop in two places.
6. **`generate_suggestions()` produces hot-file x antipattern crosses.**
   Top 3 hot files crossed with top 3 antipattern types yields up to 9
   candidates; capped at 5 after the historical S1/S2 reservation. This
   is what makes "hot files become targets" (verifier finding 5).
7. **Suggestion target paths stay inside `prompts/`.** Per the
   `self-modify.md` constraint, no suggestion writes a `.py`, `.json`,
   `.env`, `package.json`, or any path outside `prompts/meta/` or
   `prompts/learned/`. `apply_suggestion()` does not enforce this; the
   spec test asserts it.
8. **Template variable substitution is literal `{{var}}`.** No regex,
   no expression evaluation. Used by the `investigate-antipattern`
   template to produce per-pair rationales.

## Public functions

```python
def analyze(journal: list[dict]) -> dict
def generate_suggestions(analysis: dict) -> list[dict]
def cove_vote(suggestion: dict, analysis: dict) -> dict   # signature changed in Fas 1
def apply_suggestion(suggestion: dict) -> None
```

## Adversarial matrix

See `backend/specs/test_autonomous_cycle.py`. Cases cover each of the
seven Opus-flagged meta-bugs as a regression test plus the cross-product
generation, idempotent guard, and the no-op outcome rule.
