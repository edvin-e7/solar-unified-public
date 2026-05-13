# detection_escalate — active learning escalation wrapper

`backend/services/detection_escalate.py`

## Public API

```python
async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict
```

Drop-in replacement for `detection_model.detect`. Implements a "Teacher-Student" pattern where a fast, low-confidence "embed" model escalates to a more capable teacher.

## Invariants

I1. **Pass-through by default:** If `ESCALATE_ON_LOW_CONFIDENCE` is not `1`, the module behaves as a no-op wrapper returning `detection_model.detect` results directly.

I2. **Selective Escalation:** Escalation is only attempted if the primary verdict's backend is `"embed"`. Results from `"ml"`, `"gemini"`, or others never escalate.

I3. **Confidence Narrowing:** Escalation only triggers if primary confidence is borderline: `abs(confidence - 0.5) < ESCALATE_BAND`. The band is clamped to `[0.0, 0.5]` (default 0.2).

I4. **Deduplication:** Uses an LRU cache (max 4096) of 16-char SHA-1 image hashes to prevent re-escalating the same image within `ESCALATE_MIN_INTERVAL_S` (default 60s).

I5. **No-Break Guarantee:** Any exception during teacher resolution, availability check, or teacher inference is caught; the service MUST fall back to the primary verdict.

I6. **Implicit Labelling:** Successful escalations trigger a side-effect: the image is saved to `data/images/escalation/` and the teacher verdict is recorded via `detection_label_log` for future model training.

I7. **Teacher Availability:** The teacher (configured via `ESCALATE_TEACHER`, default `"moondream"`) is only consulted if its `is_available()` check returns `True`.

I8. **Metadata Injection:** Successful escalation results are augmented with `escalated_from` (original backend) and `primary_confidence` fields to maintain auditability.

## Adversarial test matrix

| Scenario | Expected Behavior |
| :--- | :--- |
| `ESCALATE_BAND=0.6` | Band is clamped to 0.5 internally; escalation happens for all `embed` results. |
| Teacher `is_available() == False` | Returns primary verdict; logs INFO. |
| Teacher raises `Exception` | Returns primary verdict; logs WARNING. Escalation never breaks the request. |
| `ESCALATE_MIN_INTERVAL_S=0` | Deduplication is disabled; every borderline request triggers escalation. |
| Rapid repeat of same image | First request escalates; subsequent requests within interval return `embed` verdict. |
| `ESCALATE_TEACHER` is unknown | Logs WARNING on the first attempt; falls back to primary verdict. |
| `detection_label_log` fails | Label recording fails silently; request returns teacher result successfully. |
| Primary backend is not `"embed"` | Returns primary result immediately, ignoring confidence/band. |
