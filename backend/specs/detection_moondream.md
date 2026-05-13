# detection_moondream — Moondream vision-LLM via local Ollama

`backend/services/detection_moondream.py`

## Public API

```python
def is_available() -> bool
async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict
```

Drop-in replacement for Gemini detection. Hits a local Ollama daemon. No API key required.

## Invariants

I1. `is_available()` is synchronous and must never raise. Returns `False` on network failure, daemon timeout (>1.5s), or if the model is not found in the daemon's local tags.

I2. `detect()` returns a standardized `DetectionResult` dictionary with `backend: "moondream"`.

I3. `has_panels` is gated by `THRESHOLD = 0.5`. Even if the model says true, the verdict is `False` if reported confidence is lower.

I4. `has_panels` is `True` only if `panel_area_m2 > 0`. If the model reports a positive verdict but fails to provide a valid area, the verdict is withheld (`False`).

I5. `roof_area_m2` mirrors `panel_area_m2`. (Limitation of current Moondream prompt/capability).

I6. Response parsing supports JSON in code fences (```json ... ```) or raw text containing a JSON object. Raises `RuntimeError` if no JSON-like structure is found.

I7. Backend configuration via environment variables: `OLLAMA_HOST`, `MOONDREAM_MODEL`, and `MOONDREAM_TIMEOUT_S`.

I8. SSRF guard: `OLLAMA_HOST` is rstripped. `image_bytes` are base64 encoded before transmission.

## Adversarial test matrix

> **Required cases:**
> - Ollama daemon unreachable → `is_available() -> False`; `detect() -> RuntimeError`
> - Model not pulled → `is_available() -> False`; `detect() -> RuntimeError` (404/400 from Ollama)
> - Model returns empty string → `detect() -> RuntimeError`
> - Model returns valid JSON but `confidence < 0.5` → `has_panels: False`
> - Model returns valid JSON but `panel_area_m2: 0` → `has_panels: False`
> - Model returns malformed JSON string (no braces) → `detect() -> RuntimeError`
> - Network timeout during inference → `detect() -> RuntimeError` (wrapped `httpx.TimeoutException`)
