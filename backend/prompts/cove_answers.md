# cove_answers.md

[Prompt content abstracted for IP protection]

This is one of the prompts driving solar-unified's autonomous agent loop.
Full prompt content is maintained in a private fork to protect engineering
IP. The calling convention and surrounding code are public.

## How prompts are used

Prompts in `backend/prompts/*.md` are loaded by `backend/prompts_loader.py`
and rendered with template variables (e.g. `{address}`, `{score}`).
They are dispatched to LLM backends (Gemini API or Ollama) through the
agent system.

## To use this codebase with your own prompts

Replace this file with your own Markdown content. The pipeline will pick
up changes on the next prompt-loader invocation.
