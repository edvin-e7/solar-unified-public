# Spec: `pattern_detector` — journal → actionable patterns

**Kontrakt**: en ren läs-analys. In: senaste `lookback` journal-entries. Ut:
strukturerade pattern-dicts som `ImprovementGenerator` kan grena på.

## Why

Memory-flaggad som skör (`pattern-detector-schema.md` — "exact journal shape
required or pattern_detector emits 0"). Varje pattern-emission binder tyst mot
journal-metadata-nycklar (`metadata.avg_confidence`, `metadata.rate`) + phase-
strängar (`data-gathering`, `enrichment`, `data-validator`). Ändrar någon
uppströms-writer en nyckel eller phase-sträng → pattern_detector emitterar 0 →
hela autonomous-learning-loopen stannar tyst. Ingen larmar.

Enligt CLAUDE.md rule 12 (spec-first + matrix): kontraktet måste ligga i spec,
regressionsguardas av matris. Nya uppströmsändringar bryter matrisen, inte
produktionen.

## Public API

```python
class PatternDetector:
    name = "pattern_detector"

    def detect_patterns(self, lookback: int = 100) -> dict[str, Any]: ...
```

Return shape:

```python
{
    "analyzed": int,          # antal entries i fönstret
    "patterns_found": int,    # len(patterns)
    "patterns": [
        {
            "name": str,              # se "Emission rules"
            "severity": "low" | "medium" | "high",
            "frequency": int,         # matches i fönstret
            "description": str,       # human-readable
            "suggestion": str,        # action hint
        },
        ...
    ],
}
```

## Journal schema dependency (load-bearing)

`detect_patterns` läser `learning_journal.entries()` som returnerar dicts med
fält: `ts, phase, outcome, lesson, files, error, metadata`. Pattern-emission
bygger på EXAKT dessa nycklar — brytning = tyst 0-emission.

Avtalet per pattern:

| Pattern | phase | outcome | metadata-nyckel | tröskel | count-krav |
|---|---|---|---|---|---|
| `low_detection_confidence` | `data-gathering` | — | `avg_confidence` | `< 0.65` | `>= 3` |
| `low_enrichment_rate` | `enrichment` | — | `rate` | `< 0.8` | `>= 2` |
| `high_validation_rejection` | `data-validator` | `failed` \| `error` | — | — | `>= 2` |
| `repeated_errors_{phase}` | (alla) | `error` | — | — | `>= 3` per phase |

## Invariants

1. **Tomt journal → tomma patterns.** `entries() == [] → patterns == [] ∧
   analyzed == 0 ∧ patterns_found == 0`. Inget crash.
2. **Saknad metadata-nyckel ≠ crash.** Om entry har `phase=data-gathering` men
   ingen `metadata.avg_confidence` → default 1.0 (inte < 0.65) → INTE räknad.
   Garanterat av `(meta := e.get("metadata", {})).get("avg_confidence", 1.0)`.
3. **Trösklar är strikt mindre än (`<`), inte `<=`.** `avg_confidence == 0.65`
   → INTE matchad. `rate == 0.8` → INTE matchad. Edge-respekterat.
4. **Count-trösklar är `>=`.** `low_conf_count == 3` → emit. `== 2` → ingen
   emit. `low_enrich_count == 2` → emit. `== 1` → ingen. `validation_rejections
   == 2` → emit. `repeated_errors_X == 3` → emit.
5. **Severity-klassning deterministisk.** `low_detection_confidence`:
   `low_conf_count > 10 ? "high" : "medium"` (never "low"). Övriga fixed.
   `repeated_errors_{phase}` alltid "high".
6. **Alla fyra pattern kan koexistera.** Samma `recent`-fönster kan trigga
   alla 4. Ingen ömsesidig exklusion. `patterns_found` = antal emitterade.
7. **`repeated_errors_{phase}` namn är dynamiskt.** Phase-strängen skjuts in
   rakt: `f"repeated_errors_{phase}"`. Gäller även `phase == "unknown"` när
   entry saknar `phase`-fält.
8. **Lookback-klippning.** `entries[-lookback:]` — äldre entries utanför
   fönstret påverkar inte. `lookback` > antalet entries → hela listan används.
   `lookback == 0` → tomt fönster → 0 patterns.
9. **Read-only.** `detect_patterns` skriver INGET. Ingen journal-record. Ingen
   disk-write. Idempotent — två anrop på samma journal → identisk output.
10. **Phase-strängar är case-sensitive.** `Data-Gathering` ≠ `data-gathering`.
    Brytning = 0 emission = upstream-writer-regression (matris fångar).

## Out of scope

- Root-cause-analys (PatternDetector rapporterar frekvens, inte orsak).
- LLM-baserad trend-detection (framtida `PatternDetectorV2`).
- Cross-pattern-correlation (t.ex. "enrichment + validation samma cykel").

## Regression risks this matrix guards against

- Uppströms-writer renamear `metadata.avg_confidence` → `metadata.confidence`.
  Matrisen emitterar 0 → test-fail → refactorer måste migrera detector.
- Ny phase `"data-validation"` (med `-tion`) introduceras av writer som tänkte
  matcha — matris kräver exakt `"data-validator"` → test-fail signalerar
  drift.
- Någon flyttar tröskel `0.65 → 0.7` eller count `3 → 5` "tyst" — matris
  boundary-test fail.
