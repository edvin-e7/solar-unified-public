# services/gemini.py — provider switch

The wrapper exposes `generate(prompt, *, model, image_bytes, phase)` and
`generate_json(...)` as the single LLM entry point. A provider switch routes
each call to either Google Gemini (`google-genai` SDK) or a local Ollama
instance, keeping every caller (8 agent modules + cove_verifier + scanner)
unchanged.

## Public API

```python
async def generate(prompt: str, *, model="gemini-2.5-flash",
                   image_bytes: bytes | None = None,
                   phase="generate") -> str
async def generate_json(prompt: str, *, model="gemini-2.5-flash",
                        image_bytes: bytes | None = None,
                        phase="generate_json") -> Any
```

Sync variants `_generate_sync` / `_generate_json_sync` mirror the signatures
for scripts that cannot `await`.

## Routing inputs

| Env var               | Default            | Effect                                       |
| --------------------- | ------------------ | -------------------------------------------- |
| `LLM_PROVIDER`        | `gemini`           | `ollama` to route to local; anything else routes to Gemini |
| `OLLAMA_HOST`         | `http://localhost:11434` | Ollama daemon HTTP endpoint            |
| `OLLAMA_TEXT_MODEL`   | `qwen2.5:1.5b`     | Used when `image_bytes is None`              |
| `OLLAMA_VISION_MODEL` | `moondream`        | Used when `image_bytes is not None`          |

## Invariants

1. **Default path unchanged.** With `LLM_PROVIDER` unset or `gemini`, the
   public functions still call `genai.Client(...).models.generate_content`.
2. **Provider isolation.** With `LLM_PROVIDER=ollama`, the Gemini SDK is
   never constructed and no `GEMINI_API_KEY` is required.
3. **Vision routes to vision model.** When `image_bytes is not None` in
   ollama mode, the request body sets `model = $OLLAMA_VISION_MODEL` and
   includes a base64 `images:[..]` field per Ollama's `/api/generate` schema.
4. **Text routes to text model.** When `image_bytes is None` in ollama mode,
   the request uses `$OLLAMA_TEXT_MODEL` and no `images` field.
5. **Streaming disabled.** Ollama requests always include `stream: false` so
   the response field is a single string.
6. **Log fidelity.** `prompt_log.jsonl` records the *actual provider+model*
   that served the call: `ollama:<model>` in ollama mode, the original gemini
   model name otherwise. Latency, phase, and image-attached flag are
   recorded for both providers.
7. **JSON extraction is provider-agnostic.** `_extract_json` handles bare
   JSON (Ollama default) and fenced code blocks (Gemini default).
8. **Unreachable daemon raises.** When `OLLAMA_HOST` is unreachable, the
   call raises `httpx.ConnectError` (or subclass), surfacing through
   `generate()` with `record_prompt(response_kind="error", ...)`.

## Adversarial matrix

See `backend/specs/test_gemini_provider.py`. Cases cover happy path (text +
JSON), model resolution in both modes, vision model routing, and
unreachable-daemon error transparency. All cases must pass before a
backend ships with the Ollama path enabled.
