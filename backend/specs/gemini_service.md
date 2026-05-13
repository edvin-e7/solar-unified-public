# Gemini Service Specification

`backend/services/gemini.py`

Single entry point for all LLM interactions (text and vision). Abstracts provider switching (Gemini/Ollama), handles async offloading, and provides robust JSON extraction.

## Public API

### `async generate(...) -> str`
Primary entry point for text generation.
- **Parameters:**
  - `prompt: str`: The instruction to the LLM.
  - `model: str`: Gemini model string (default: `gemini-2.5-flash`).
  - `image_bytes: bytes | None`: Optional JPEG data for vision tasks.
  - `phase: str`: Label for prompt logging (default: `generate`).
- **Returns:** Raw string response from the LLM.
- **Behavior:** Offloads blocking SDK calls to `asyncio.to_thread`.

### `async generate_json(...) -> Any`
Wraps `generate` and extracts a JSON object/array.
- **Parameters:** Same as `generate`.
- **Returns:** Parsed Python dictionary or list.
- **Errors:** Raises `json.JSONDecodeError` if no valid JSON is found.

## Invariants

- **I1 (Security):** Must raise `RuntimeError` if `ALLOW_EXTERNAL_LLM != "1"` when using Gemini provider.
- **I2 (Authentication):** Must raise `RuntimeError` if `GEMINI_API_KEY` is missing when using Gemini provider.
- **I3 (Logging):** EVERY call (success or failure) MUST be recorded via `record_prompt` with accurate latency and model resolution.
- **I4 (Provider Parity):** `generate` must transparently switch between `gemini` and `ollama` based on `LLM_PROVIDER` env var.
- **I5 (Vision Support):** If `image_bytes` is provided, the payload must include the image data (Gemini `Part` or Ollama `images` array).
- **I6 (JSON Robustness):** `generate_json` must handle code fences (````json ... ````), leading/trailing prose, and "Extra data" (text after the JSON block).
- **I7 (Async Safety):** Sync SDK calls MUST NOT block the event loop; they must run in `asyncio.to_thread`.
- **I8 (Resilience):** Ollama calls must use a generous timeout (default 300s) to allow for cold-start model loading.

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| **API key expired/invalid** | Raise `Exception`, log failure via `record_prompt` with `response_kind="error"`. | I3 |
| **Ollama cold-start (>30s)** | Wait up to 300s without timing out. | I8 |
| **LLM returns prose + JSON** | `generate_json` successfully extracts the JSON portion and ignores prose. | I6 |
| **LLM returns malformed JSON** | `generate_json` raises `json.JSONDecodeError`. | I6 |
| **Vision call with PNG** | Service treats bytes as `image/jpeg` (current implementation default). | I5 |
| **External calls disabled** | Raise `RuntimeError` immediately before calling provider. | I1 |
| **Rapid concurrent calls** | `asyncio.to_thread` prevents event loop starvation. | I7 |
| **Empty LLM response** | `_extract_json` raises `ValueError("empty response")`. | I6 |
