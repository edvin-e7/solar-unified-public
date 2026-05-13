"""Load versioned system prompts from backend/prompts/*.md.

Each prompt file has YAML frontmatter with `name`, `version`, `model`, `variables`,
`description`. The body uses {{var}} for substitution.

Usage:
    from prompts_loader import load, render
    tpl = load("detection")
    rendered = render(tpl, {"address": "Björkgatan 4, Uppsala"})
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise RuntimeError("pyyaml required: pip install pyyaml") from e

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass
class Prompt:
    name: str
    version: str
    model: str
    description: str
    variables: list[str] = field(default_factory=list)
    body: str = ""


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def load(name: str) -> Prompt:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"No prompt named {name!r} at {path}")
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER.match(text)
    if not m:
        raise ValueError(f"Prompt {name!r} missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    return Prompt(
        name=meta.get("name", name),
        version=str(meta.get("version", "0.0")),
        model=meta.get("model", "gemini-2.5-flash"),
        description=meta.get("description", ""),
        variables=list(meta.get("variables", [])),
        body=m.group(2).strip(),
    )


def render(prompt: Prompt, variables: dict[str, Any]) -> str:
    missing = [v for v in prompt.variables if v not in variables]
    if missing:
        raise ValueError(f"Prompt {prompt.name!r} missing variables: {missing}")

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(variables.get(key, match.group(0)))

    return _PLACEHOLDER.sub(sub, prompt.body)


def list_prompts() -> list[Prompt]:
    return [load(p.stem) for p in sorted(PROMPTS_DIR.glob("*.md"))]
