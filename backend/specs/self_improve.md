# Self-Improvement Orchestrator Spec

## Public API

### Functions

- **`main() -> int`**
  The main entrypoint for the autonomous improvement cycle. Orchestrates the flow from analysis to commit.
  - **Returns**: `0` on success or no action needed, `1` on failure or error.

- **`get_patterns() -> dict`**
  Analyzes the `learning_journal` to extract success rates and recent antipatterns.

- **`test_baseline() -> bool`**
  Runs the project-wide verification suite (`verify_all.py`).
  - **Returns**: `True` if all tests pass.

- **`suggest_improvement(patterns: dict) -> dict | None`**
  Heuristically generates a fix suggestion based on observed antipatterns.

---

## Invariants

- **I1 [Stability First]**: No code changes MUST be proposed if the existing system baseline is failing (`test_baseline() == False`).
- **I2 [Safe Success Margin]**: The autonomous loop MUST only suggest improvements if the aggregate system success rate is $\ge 90\%$.
- **I3 [CoVe Enforcement]**: All suggestions MUST pass the Chain-of-Verification process with sufficient confidence before any git operations occur.
- **I4 [Branch Isolation]**: Every verified improvement MUST be applied to a new, isolated branch named `auto-improve-<date>` to allow for human review before merge.
- **I5 [Outcome Accountability]**: The system MUST log the final result of every cycle (passed, failed, or error) to the `learning_journal`.
- **I6 [Atomic Git Workflow]**: Any failure in the git lifecycle (branching, staging, committing, or pushing) MUST result in a logged error and immediate cycle termination.
- **I7 [Knowledge Reinforcement]**: Suggestions MUST be directly linked to documented "antipatterns" found in previous failures to ensure the system is learning from its mistakes.
- **I8 [Zero-Manual-Intervention]**: The cycle MUST be capable of running fully unattended in a CI/CD environment (e.g., via GitHub Actions).

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `verify_all.py` fails before cycle | Skips cycle; prints warning. | I1 |
| Success rate is 89.9% | No improvements suggested. | I2 |
| CoVe confidence is 0.74 | Improvement rejected; failure recorded in journal. | I3 |
| Git branch name collision | `git checkout -b` fails; cycle records "error" and terminates. | I6 |
| No antipatterns in journal | Cycle terminates gracefully with "No safe improvements". | I7 |
| Unicode/CP1252 error in journal | Triggers the specific "UTF-8 encoding" suggestion logic. | I7 |
| Remote push forbidden | Records error in journal; branch remains local. | I6 |
