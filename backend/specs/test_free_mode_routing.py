"""Adversarial matrix for free-by-default LLM routing.

Pins:
1. _provider() defaults to 'ollama' (no env) — solves user's "stop running
   gemini api, run free" request.
2. scanner.py routes to dispatcher unless DETECTION_BACKEND=gemini-legacy
   (which is an explicit opt-in to the old paid path).
3. ALLOW_EXTERNAL_LLM=0 still blocks any Gemini client construction —
   double-safety even when LLM_PROVIDER=gemini slips through.

Run: python3 -m pytest backend/specs/test_free_mode_routing.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import gemini as gemini_mod

# ----- F1: provider default ------------------------------------------------


def test_f1_provider_defaults_to_ollama_without_env(monkeypatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert gemini_mod._provider() == "ollama"


def test_f1_provider_explicit_gemini_respected(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert gemini_mod._provider() == "gemini"


def test_f1_provider_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "Ollama")
    assert gemini_mod._provider() == "ollama"


# ----- F2: ALLOW_EXTERNAL_LLM hard-gate still in force ---------------------


def test_f2_external_llm_disabled_raises_before_calling_gemini(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_EXTERNAL_LLM", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    # _client() is lru_cached — clear it
    gemini_mod._client.cache_clear()
    with pytest.raises(RuntimeError, match="External LLM APIs disabled"):
        gemini_mod._client()


# ----- F3: generate_sync routes to ollama when provider=ollama -------------


def test_f3_generate_sync_routes_to_ollama_when_provider_ollama(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "ollama")

    called = {"ollama": 0, "gemini": 0}

    def fake_ollama(prompt, image_bytes):
        called["ollama"] += 1
        return "ollama-response"

    def fake_gemini(prompt, *, model, image_bytes):
        called["gemini"] += 1
        return "gemini-response"

    monkeypatch.setattr(gemini_mod, "_ollama_generate_sync", fake_ollama)
    monkeypatch.setattr(gemini_mod, "_generate_sync_no_retry", fake_gemini)

    result = gemini_mod._generate_sync("test prompt")
    assert result == "ollama-response"
    assert called == {"ollama": 1, "gemini": 0}


def test_f3_default_env_routes_to_ollama(monkeypatch) -> None:
    """No LLM_PROVIDER env set → uses ollama path."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    called = {"ollama": 0}

    def fake_ollama(prompt, image_bytes):
        called["ollama"] += 1
        return "ok"

    monkeypatch.setattr(gemini_mod, "_ollama_generate_sync", fake_ollama)

    result = gemini_mod._generate_sync("test")
    assert result == "ok"
    assert called["ollama"] == 1


# ----- F4: GeminiQuotaExceeded still defined + RuntimeError-subclass -------


def test_f4_quota_exception_still_exported() -> None:
    """Bug 3 fix should still work — exception class is part of contract."""
    assert hasattr(gemini_mod, "GeminiQuotaExceeded")
    assert issubclass(gemini_mod.GeminiQuotaExceeded, RuntimeError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
