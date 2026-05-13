# Prompts Loader Service Spec

## Public API

### Functions

- **`load(name: str) -> Prompt`**
  Loads a versioned system prompt from `backend/prompts/<name>.md`.
  - Parses YAML frontmatter for metadata (model, version, variables).
  - **Returns**: A `Prompt` dataclass instance.

- **`render(prompt: Prompt, variables: dict[str, Any]) -> str`**
  Replaces `{{variable}}` placeholders in the prompt body with provided values.
  - **Raises**: `ValueError` if required variables (defined in frontmatter) are missing.

- **`list_prompts() -> list[Prompt]`**
  Lists all available prompts in the `prompts/` directory.

### Data Types

- **`Prompt` (Dataclass)**:
  - `name`: Prompt identifier.
  - `version`: Version string.
  - `model`: Target LLM (e.g., `gemini-2.5-flash`).
  - `variables`: List of required placeholder keys.
  - `body`: The raw prompt text with placeholders.

---

## Invariants

- **I1 [Mandatory Frontmatter]**: Every prompt file MUST begin with a valid YAML frontmatter section delimited by `---`.
- **I2 [Safe Template Rendering]**: Placeholder replacement MUST be case-sensitive and match the `{{key}}` syntax exactly.
- **I3 [UTF-8 Integrity]**: All prompt files MUST be read as UTF-8 to preserve international characters and emojis.
- **I4 [Strict Variable Validation]**: `render` MUST verify that all variables listed in the frontmatter `variables` list are present in the input dictionary before performing any substitutions.
- **I5 [Default Model Steering]**: If the frontmatter does not specify a `model`, it MUST default to `gemini-2.5-flash`.
- **I6 [Atomic File Access]**: Prompts SHOULD be loaded from disk on each call (or rely on OS-level file caching) to ensure updates to `.md` files take effect without a server restart.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Variable missing in `render` call | Raises `ValueError` listing missing keys. | I4 |
| Missing YAML frontmatter | Raises `ValueError: Prompt '...' missing YAML frontmatter`. | I1 |
| Prompt file not found | Raises `FileNotFoundError`. | I1 |
| Extra variables passed to `render` | Ignored; only placeholders matching `{{key}}` are substituted. | I2 |
| Body contains double braces `{{...}}` | Correctly identified as placeholders. | I2 |
| YAML contains syntax error | `yaml.safe_load` raises error; service bubbles it up. | I1 |
