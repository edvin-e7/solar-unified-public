# Next iteration prompt (generated 2026-04-27T15:49:43.755640+00:00)

## Top priority: drive `spec_coverage` from 27 → 0

**Why blocking felfri:** missing spec = no adversarial matrix = future regression
**Ledger entry:** `039461ac8888` (auto-opened by verify_v2)

## Approach
1. Get list of 27 missing modules from verify_v2 evidence
2. Prioritize: api/* (user-facing) → services/* → agents/* → executors/*
3. For each: write `backend/specs/<module>.md` (numbered invariants) + `backend/specs/test_<module>.py` (adversarial matrix)
4. Per CLAUDE.md rule 12: matrix must include explicit stress cases (concurrency, crash-replay, paraphrase, stopwords, Unicode, empty, boundary, adversarial)
5. Implement until matrix green

## Predicted state after this iteration
```json
{
  "bare_except_audit": 13,
  "silent_return_audit": 0,
  "prd_parity": 10,
  "opt_drift": 4,
  "spec_coverage": 0
}
```

## Other failing stages (deferred to subsequent iterations)
- `bare_except_audit` (13 bugs) — ledger cf57f0c07274
- `prd_parity` (10 bugs) — ledger 0a6b303ecefe
- `opt_drift` (4 bugs) — ledger 24b9a29ad02a

## Self-eval gate (CoVe — 5 Q&A) before executing this prompt:
1. Is this the highest-leverage failure right now? (priority × bug_count)
2. Does the approach respect CLAUDE.md rule 4 (no shortcuts)?
3. Will completing this unblock subsequent stages, or is it independent?
4. Are there prior ledger attempts on this stage that already failed?
5. Does the predicted state assume too much (e.g. dropping to 0 in one iteration when realistic is partial)?

If any answer is uncertain, lower confidence and revise prompt before next loop executes.

## CoVe self-eval
```json
{
  "verified": true,
  "confidence": 1.0,
  "q_and_a": [
    {
      "q": "concrete top action?",
      "a": true,
      "weight": 0.2
    },
    {
      "q": "ledger entry cited?",
      "a": true,
      "weight": 0.15
    },
    {
      "q": "numbered approach?",
      "a": true,
      "weight": 0.15
    },
    {
      "q": "predicted next state?",
      "a": true,
      "weight": 0.2
    },
    {
      "q": "references project rules?",
      "a": true,
      "weight": 0.3
    }
  ]
}
```
