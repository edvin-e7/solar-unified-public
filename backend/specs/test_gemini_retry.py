"""Adversarial matrix for services/gemini.py 429 retry + GeminiQuotaExceeded.

Fixes docs/BUGS.md Bug 3 — Gemini free-tier 429 RESOURCE_EXHAUSTED silently
stalls scheduled learning cycles. Retry policy + typed exception lets callers
branch instead of looping on the same error.

Run: python3 -m pytest backend/specs/test_gemini_retry.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import gemini

# ----- C1: _is_rate_limit_error detection matrix ----------------------------


class _Exc429:
    def __init__(self, msg: str = "", *, status_code: int | None = None, code: int | None = None):
        self.msg = msg
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code

    def __str__(self) -> str:
        return self.msg


def _make_exc(**kwargs) -> Exception:
    """Build a generic Exception with the attributes _is_rate_limit_error looks at."""
    exc = Exception(kwargs.pop("msg", ""))
    for k, v in kwargs.items():
        setattr(exc, k, v)
    return exc


def test_c1_status_code_429_is_rate_limit() -> None:
    assert gemini._is_rate_limit_error(_make_exc(msg="x", status_code=429))


def test_c1_code_429_is_rate_limit() -> None:
    assert gemini._is_rate_limit_error(_make_exc(msg="x", code=429))


def test_c1_message_429_is_rate_limit() -> None:
    assert gemini._is_rate_limit_error(Exception("HTTP 429 too many requests"))


def test_c1_resource_exhausted_underscore() -> None:
    assert gemini._is_rate_limit_error(Exception("RESOURCE_EXHAUSTED"))


def test_c1_resource_exhausted_space() -> None:
    assert gemini._is_rate_limit_error(Exception("status: resource exhausted"))


def test_c1_quota_exceeded() -> None:
    assert gemini._is_rate_limit_error(Exception("Free-tier quota exceeded for project"))


def test_c1_quota_limit() -> None:
    assert gemini._is_rate_limit_error(Exception("Daily quota limit reached"))


def test_c1_rate_limit_dash() -> None:
    assert gemini._is_rate_limit_error(Exception("X-RateLimit hit: rate-limit"))


def test_c1_auth_error_not_rate_limit() -> None:
    # Auth failures should NOT trigger retry — caller's API key is broken
    assert not gemini._is_rate_limit_error(Exception("403 PERMISSION_DENIED: API key invalid"))


def test_c1_404_not_rate_limit() -> None:
    assert not gemini._is_rate_limit_error(_make_exc(msg="not found", status_code=404))


def test_c1_random_500_not_rate_limit() -> None:
    assert not gemini._is_rate_limit_error(_make_exc(msg="internal", status_code=500))


# ----- C2: _backoff_delay_seconds bounded ----------------------------------


def test_c2_backoff_attempt_1_below_base() -> None:
    # attempt 1 → uniform(0, base) where base=1.0 by default
    for _ in range(50):
        d = gemini._backoff_delay_seconds(1)
        assert 0 <= d <= gemini._RETRY_BASE_S


def test_c2_backoff_capped_at_max_delay() -> None:
    # attempt 1000 → would explode without cap; verify cap
    for _ in range(20):
        d = gemini._backoff_delay_seconds(1000)
        assert 0 <= d <= gemini._RETRY_MAX_DELAY_S


# ----- C3: retry behavior in _generate_sync --------------------------------


def test_c3_success_on_first_attempt_no_retry(monkeypatch) -> None:
    """Happy path — no retry, returns immediately."""
    call_count = {"n": 0}

    def fake_call(prompt, *, model, image_bytes):
        call_count["n"] += 1
        return "ok"

    monkeypatch.setattr(gemini, "_generate_sync_no_retry", fake_call)
    monkeypatch.setattr(gemini, "_provider", lambda: "gemini")

    result = gemini._generate_sync("hello", model="gemini-2.5-flash")
    assert result == "ok"
    assert call_count["n"] == 1


def test_c3_429_then_success_retries(monkeypatch) -> None:
    """First call raises 429, second succeeds — retry should kick in."""
    attempts = {"n": 0}

    def flaky(prompt, *, model, image_bytes):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise Exception("HTTP 429 RESOURCE_EXHAUSTED")
        return "recovered"

    monkeypatch.setattr(gemini, "_generate_sync_no_retry", flaky)
    monkeypatch.setattr(gemini, "_provider", lambda: "gemini")
    # Make backoff instant to keep test fast
    monkeypatch.setattr(gemini, "_backoff_delay_seconds", lambda a: 0.001)

    result = gemini._generate_sync("p", model="gemini-2.5-flash")
    assert result == "recovered"
    assert attempts["n"] == 2


def test_c3_persistent_429_raises_quota_exceeded(monkeypatch) -> None:
    """All retries 429 → raises GeminiQuotaExceeded (not bare Exception)."""
    attempts = {"n": 0}

    def always_429(prompt, *, model, image_bytes):
        attempts["n"] += 1
        raise Exception("HTTP 429 quota exceeded")

    monkeypatch.setattr(gemini, "_generate_sync_no_retry", always_429)
    monkeypatch.setattr(gemini, "_provider", lambda: "gemini")
    monkeypatch.setattr(gemini, "_backoff_delay_seconds", lambda a: 0.001)
    monkeypatch.setattr(gemini, "_RETRY_MAX_ATTEMPTS", 3)

    with pytest.raises(gemini.GeminiQuotaExceeded) as excinfo:
        gemini._generate_sync("p", model="gemini-2.5-flash")

    assert attempts["n"] == 3
    assert excinfo.value.attempts == 3
    assert excinfo.value.last_error is not None
    assert "429" in str(excinfo.value.last_error)


def test_c3_non_429_error_no_retry(monkeypatch) -> None:
    """Non-rate-limit exception should propagate immediately — no retry."""
    attempts = {"n": 0}

    def auth_fail(prompt, *, model, image_bytes):
        attempts["n"] += 1
        raise Exception("403 PERMISSION_DENIED: invalid key")

    monkeypatch.setattr(gemini, "_generate_sync_no_retry", auth_fail)
    monkeypatch.setattr(gemini, "_provider", lambda: "gemini")
    monkeypatch.setattr(gemini, "_backoff_delay_seconds", lambda a: 0.001)

    with pytest.raises(Exception) as excinfo:
        gemini._generate_sync("p", model="gemini-2.5-flash")

    # Should NOT be GeminiQuotaExceeded — just the original auth error
    assert not isinstance(excinfo.value, gemini.GeminiQuotaExceeded)
    assert "403" in str(excinfo.value)
    # Only 1 attempt — no retry
    assert attempts["n"] == 1


def test_c3_ollama_provider_skips_retry(monkeypatch) -> None:
    """Ollama backend has no quota → no retry wrapper, calls direct path."""
    monkeypatch.setattr(gemini, "_provider", lambda: "ollama")
    monkeypatch.setattr(gemini, "_ollama_generate_sync", lambda p, ib: "local-ok")

    result = gemini._generate_sync("p", model="gemini-2.5-flash")
    assert result == "local-ok"


# ----- C4: GeminiQuotaExceeded exception shape -----------------------------


def test_c4_quota_exception_carries_attempt_count() -> None:
    e = gemini.GeminiQuotaExceeded("test", attempts=5, last_error=ValueError("inner"))
    assert e.attempts == 5
    assert isinstance(e.last_error, ValueError)
    assert "test" in str(e)


def test_c4_quota_exception_is_runtimeerror_subclass() -> None:
    # Callers can catch broad RuntimeError as before — backwards compatible
    assert issubclass(gemini.GeminiQuotaExceeded, RuntimeError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
