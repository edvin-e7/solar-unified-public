"""Adversarial matrix for _check_llm_health startup hook.

Pins:
1. Provider != ollama → emits informational log, no Ollama probe
2. Provider = ollama + Ollama reachable + model present → INFO with model count
3. Provider = ollama + Ollama reachable + model MISSING → WARN with pull-cmd
4. Provider = ollama + Ollama unreachable → WARN with install-cmd
5. Never raises (must not crash FastAPI startup)

Run: python3 -m pytest backend/specs/test_llm_startup_health.py -v
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class _FakeResp:
    def __init__(self, json_data, status=200):
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._json


class _FakeClient:
    def __init__(self, *, payload=None, raise_on_get=None):
        self._payload = payload
        self._raise = raise_on_get

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url, **kw):
        if self._raise:
            raise self._raise
        return _FakeResp(self._payload)


@pytest.fixture
def main_module():
    """Re-import main with env safely defaulted so import succeeds in test."""
    os.environ["ALLOW_BOOT_WITHOUT_KEYS"] = "1"
    sys.modules.pop("main", None)
    import main  # type: ignore
    return main


def _run(coro):
    return asyncio.run(coro)


def test_g1_non_ollama_provider_skips_probe(main_module, monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    with caplog.at_level(logging.INFO, logger="solar_unified.boot"):
        _run(main_module._check_llm_health())
    assert any("free-mode disabled" in r.getMessage() for r in caplog.records)


def test_g2_ollama_reachable_with_vision_model_logs_info(main_module, monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "moondream")

    import httpx
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(payload={"models": [{"name": "moondream:latest"}, {"name": "qwen2.5:1.5b"}]}),
    )

    with caplog.at_level(logging.INFO, logger="solar_unified.boot"):
        _run(main_module._check_llm_health())

    msgs = [r.getMessage() for r in caplog.records]
    assert any("free-mode" in m and "moondream" in m for m in msgs)


def test_g3_ollama_reachable_but_vision_model_missing_warns(main_module, monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "moondream")

    import httpx
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(payload={"models": [{"name": "gemma3:1b"}]}),
    )

    with caplog.at_level(logging.WARNING, logger="solar_unified.boot"):
        _run(main_module._check_llm_health())

    assert any("missing the vision model" in r.getMessage() for r in caplog.records)
    assert any("ollama pull moondream" in r.getMessage() for r in caplog.records)


def test_g4_ollama_unreachable_warns_with_install_cmd(main_module, monkeypatch, caplog):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    import httpx
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: _FakeClient(raise_on_get=ConnectionError("daemon down")),
    )

    with caplog.at_level(logging.WARNING, logger="solar_unified.boot"):
        _run(main_module._check_llm_health())

    msgs = [r.getMessage() for r in caplog.records]
    assert any("unreachable" in m for m in msgs)
    assert any("ollama.com" in m for m in msgs)


def test_g5_health_check_never_raises_on_unexpected_error(main_module, monkeypatch):
    """Startup must not crash on any health-check exception."""
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    import httpx

    class _ExplodingClient:
        async def __aenter__(self):
            raise RuntimeError("totally unexpected explosion")

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: _ExplodingClient())

    # Must not raise — startup continues
    _run(main_module._check_llm_health())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
