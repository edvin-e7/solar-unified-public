"""Adversarial matrix for the LLM_PROVIDER switch in services/gemini.py.

Spec: backend/specs/gemini_provider.md.

Run from the backend/ directory with the venv:

    .venv/bin/python -m pytest backend/specs/test_gemini_provider.py -v

Cases 1, 2, and 6-vision require a running Ollama with `qwen2.5:1.5b` and
`moondream` pulled. They are skipped when the daemon is unreachable so the
suite stays green in CI environments without Ollama. Cases 3, 4, and 5 run
unconditionally — they exercise pure-python routing logic and an
intentionally unreachable host.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _ollama_up(host: str = "http://localhost:11434") -> bool:
    try:
        return httpx.get(f"{host}/api/version", timeout=1.0).status_code == 200
    except httpx.HTTPError:
        return False


def _gemini_in_ollama_mode():
    """Re-import services.gemini with LLM_PROVIDER=ollama set."""
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
    os.environ.setdefault("OLLAMA_TEXT_MODEL", "qwen2.5:1.5b")
    os.environ.setdefault("OLLAMA_VISION_MODEL", "moondream")
    sys.modules.pop("services.gemini", None)
    from services import gemini  # type: ignore
    return gemini


def test_resolved_model_text_in_ollama_mode():
    g = _gemini_in_ollama_mode()
    assert g._resolved_model("gemini-2.5-flash", None) == "ollama:qwen2.5:1.5b"


def test_resolved_model_vision_in_ollama_mode():
    g = _gemini_in_ollama_mode()
    assert g._resolved_model("gemini-2.5-flash", b"\xff\xd8\xff") == "ollama:moondream"


def test_resolved_model_passthrough_in_gemini_mode():
    os.environ["LLM_PROVIDER"] = "gemini"
    sys.modules.pop("services.gemini", None)
    from services import gemini as g  # type: ignore
    assert g._resolved_model("gemini-2.5-flash", None) == "gemini-2.5-flash"


def test_unreachable_ollama_raises_connect_error():
    os.environ["LLM_PROVIDER"] = "ollama"
    os.environ["OLLAMA_HOST"] = "http://127.0.0.1:1"
    sys.modules.pop("services.gemini", None)
    from services import gemini as g  # type: ignore
    with pytest.raises((httpx.ConnectError, httpx.HTTPError)):
        g._generate_sync("hi")
    os.environ["OLLAMA_HOST"] = "http://localhost:11434"


@pytest.mark.skipif(not _ollama_up(), reason="ollama daemon not running")
def test_text_generate_via_ollama_returns_output():
    g = _gemini_in_ollama_mode()
    out = asyncio.run(g.generate("Reply with exactly: PONG", phase="test"))
    assert "PONG" in out.upper(), f"unexpected output: {out!r}"


@pytest.mark.skipif(not _ollama_up(), reason="ollama daemon not running")
def test_generate_json_extracts_bare_json_from_ollama():
    g = _gemini_in_ollama_mode()
    raw = asyncio.run(
        g.generate(
            'Return ONLY a JSON object: {"ok": true}. No prose, no fences.',
            phase="test-json",
        )
    )
    parsed = g._extract_json(raw)
    assert isinstance(parsed, dict) and parsed.get("ok") is True
