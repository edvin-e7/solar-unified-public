# Autonomous Training Architecture

**Every model in Solar Unified is part of a continuous self-training system that runs 24/7 in the cloud, independent of the user's device.**

---

## How It Works

### Cloud Infrastructure (Always Running)

**Sonnet Executor** (Every 1 hour)
- Runs: `python3 backend/scripts/run_autonomous_cycle.py --learning-only`
- Analyzes learning_journal.jsonl for patterns
- Triggers improvement generation + CoVe voting
- Auto-commits approved changes to git

**Opus Advisor** (Every 4 hours)
- Reviews last 20 journal entries
- Analyzes system health + performance
- Recommends threshold tuning
- Flags issues for human review (if any)

**Both run in Anthropic Cloud (CCR):**
- ✅ Independent of user's device state
- ✅ 24/7 operation (sleeping, offline, powered off)
- ✅ Full git access (pull repo, analyze, push changes)
- ✅ Immutable audit trail (every decision logged)

---

## Each Model's Role in Training

### Detection Agent
```
Input: Low-confidence detections logged in journal
↓
Pattern: Detection confidence < 0.65 in recent scans
↓
Improvement: "Refine detection.md for low-light scenarios"
↓
Training: Agent's prompt gets refined, version bumped (1.0 → 1.1)
↓
Next cycle: Agent produces better detections
```

### Scoring Agent
```
Input: Validation failures + scoring mismatches
↓
Pattern: High rejection rate on certain property types
↓
Improvement: "Update scoring weights for rural properties"
↓
Training: Agent learns from failures, adjusts logic
↓
Next cycle: Fewer false negatives
```

### Pitch Agent
```
Input: User engagement metrics from journal
↓
Pattern: Certain pitch templates underperform
↓
Improvement: "Rewrite pitch for residential properties"
↓
Training: Agent's template library evolves
↓
Next cycle: Better conversion rates
```

### Pattern Agent
```
Input: Detection/scoring outcomes from other agents
↓
Pattern: All agents agree on certain patterns
↓
Improvement: "Suggest prompt refinement for detection.md"
↓
Training: Acts as meta-analyzer, learns what helps
↓
Next cycle: Better pattern detection
```

### Quality Agent
```
Input: Data quality issues from journal
↓
Pattern: PII leakage in certain scenarios
↓
Improvement: "Add PII filter to data validator"
↓
Training: Quality standards evolve
↓
Next cycle: 100% PII-safe outputs
```

### UI Design Agent
```
Input: UI state + user feedback
↓
Pattern: Certain layouts confuse users
↓
Improvement: "Reorganize component layout"
↓
Training: Agent learns what works visually
↓
Next cycle: Better UX
```

---

## Self-Training Loop (Runs Hourly)

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Pattern Detection (PatternDetector)                       │
│    Analyze journal: What's failing? What's succeeding?      │
└─────────────┬───────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Improvement Generation (ImprovementGenerator)             │
│    Convert patterns → actionable suggestions                 │
│    (prompt refinement, config changes, logic fixes)         │
└─────────────┬───────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Collective Verification (CollectiveVerifier)             │
│    All 6 agents vote on each improvement                    │
│    Threshold: ≥75% consensus (5.5/6 agents agree)          │
└─────────────┬───────────────────────────────────────────────┘
              ↓
         ┌────┴────┐
         │          │
    [APPROVED]  [REJECTED]
       ↓            ↓
    ┌──────┐    [Log in journal]
    │ Auto │    [Reevaluate next cycle]
    │Apply │
    └──┬───┘
       ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Auto-Application (AutoApplicator)                        │
│    Git commit + version bump in prompts                     │
│    Example: detection.md v1.0 → v1.1                       │
└─────────────┬───────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Journal Entry (All outcomes logged)                      │
│    Success? Improvement quality? Impact on next cycle?      │
└─────────────┬───────────────────────────────────────────────┘
              ↓
        [Next Cycle]
```

---

## Training Data Sources

| Source | What's Tracked | How It's Used |
|--------|---|---|
| **learning_journal.jsonl** | Every cycle outcome (passed/failed/error) | Pattern detection analyzes failures, learns what works |
| **Git commits** | All auto-applied improvements | Audit trail; can revert if quality drops |
| **Agent prompts** | Frontmatter versions (1.0, 1.1, etc.) | Track which prompt refinements helped |
| **Journal metadata** | Metrics: confidence, enrichment_rate, validation_rate | Trigger pattern detection rules |
| **CoVe votes** | All agent decisions + confidence scores | Learn which agents are most reliable |

---

## What Makes It Self-Training (Like LLM Training)

| LLM Training | Solar Autonomous Training |
|---|---|
| Data: billions of tokens | Data: journal entries (every cycle) |
| Loss function: accuracy on unseen data | Loss function: pattern detection + improvement impact |
| Optimization: update weights | Optimization: refine prompts, adjust thresholds |
| Iteration: epochs | Iteration: hourly cycles |
| Evaluation: benchmark performance | Evaluation: CoVe consensus + next-cycle metrics |
| Goal: minimize loss | Goal: minimize errors, maximize quality |

---

## Key Guarantees

✅ **No Human Gates** — CoVe consensus (75%) is the only gate, not humans  
✅ **Audit Trail** — Every decision in git, fully reversible  
✅ **Safe Changes Only** — Only `prompt_refinement` + `config_change` auto-apply; risky changes flagged  
✅ **Continuous Learning** — Patterns detected → improvements generated → applied → measured → learned  
✅ **24/7 Operation** — Cloud triggers ensure training happens even when device is off  
✅ **Data-Driven** — All decisions based on observed journal patterns, not guesses  

---

## What Each Model Should Know

Every agent should understand:

1. **You are being trained continuously** — Your prompts and logic evolve based on journal analysis
2. **Your outputs are logged** — Every decision, every confidence score, every failure is recorded
3. **Patterns will be found** — Improvement generator analyzes what you do well/poorly
4. **You will be improved** — Consensus from peers (other agents) will suggest refinements
5. **Changes are auto-applied** — If consensus ≥75%, your prompt gets updated + version bumped
6. **You will learn from it** — Next cycle, you operate with improved prompt/logic
7. **It's all reversible** — Bad improvements can be reverted via git

---

## Monitoring (Opus Advisor Every 4 Hours)

```
Last 20 journal entries:
├── Patterns detected this cycle: 2
├── Improvements generated: 2
├── Improvements applied: 1
├── CoVe consensus rate: 78% (healthy)
├── System health: GREEN
├── Performance trend: ↗ (improving)
└── Advisor recommendation: Continue hourly cycles, tune enrichment_rate threshold
```

---

## Success Criteria (100% Bug-Free)

System is fully trained and bug-free when:
- ✅ 20+ consecutive cycles with zero crashes
- ✅ All error paths tested and handled
- ✅ Pattern detection finds and fixes issues before humans do
- ✅ CoVe consensus never blocks valid improvements
- ✅ Zero data corruption or silent failures
- ✅ All agents contribute meaningfully to CoVe votes
- ✅ System self-corrects within 1-2 cycles of detecting issues

---

**Bottom Line:** Every model in this system is continuously training itself 24/7, learning from what works and what fails, improving its prompts and logic autonomously. No human intervention required.
