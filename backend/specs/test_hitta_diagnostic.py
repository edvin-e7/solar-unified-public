"""Adversarial matrix for services/hitta.py HittaEmpty diagnostic dump.

Fixes docs/BUGS.md Bug 1 (partial) — adds diagnostic logging on HittaEmpty
so the next session can see what hitta.se actually returned instead of
black-box-guessing. Full fix (multi-provider fallback, retry-with-different-
shape) requires live network testing — out of scope for autonomous bot.

Run: python3 -m pytest backend/specs/test_hitta_diagnostic.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import hitta


class _FakeResp:
    def __init__(self, text: str, *, status_code: int = 200, url: str = "https://www.hitta.se/sök") -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html"}


# ----- E1: _dump_empty_response writes html + meta when dir is set ----------


def test_e1_dump_writes_html_and_meta_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hitta, "_DIAG_DIR", tmp_path)
    resp = _FakeResp("<html>empty body</html>")
    path = hitta._dump_empty_response("Storgatan 1, Stockholm", resp.text, resp)
    assert path is not None
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "<html>empty body</html>"

    meta_path = path.with_suffix(".meta.json")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["status_code"] == 200
    assert meta["html_length"] == len("<html>empty body</html>")
    assert "address_hash" in meta
    assert len(meta["address_hash"]) == 12  # sha256 truncated to 12 chars
    # Plaintext address must NOT appear in meta — only hash
    assert "Storgatan 1" not in json.dumps(meta)
    assert "Stockholm" not in json.dumps(meta)


# ----- E2: dump disabled when _DIAG_DIR is None ----------------------------


def test_e2_dump_disabled_when_dir_none(monkeypatch) -> None:
    monkeypatch.setattr(hitta, "_DIAG_DIR", None)
    resp = _FakeResp("<html>x</html>")
    path = hitta._dump_empty_response("X", resp.text, resp)
    assert path is None


# ----- E3: dump survives filesystem errors (best-effort) -------------------


def test_e3_dump_survives_unwritable_path(tmp_path, monkeypatch) -> None:
    # Point _DIAG_DIR to a path that can't be created (file shadowing parent)
    blocker = tmp_path / "blocker"
    blocker.write_text("not a dir")  # now you can't create blocker/subdir
    monkeypatch.setattr(hitta, "_DIAG_DIR", blocker / "subdir")

    resp = _FakeResp("<html>x</html>")
    # Must return None, NOT raise — diagnostic is best-effort
    path = hitta._dump_empty_response("X", resp.text, resp)
    assert path is None


# ----- E4: meta.json captures the head of HTML for ops diagnosis -----------


def test_e4_meta_includes_html_head_for_root_cause_analysis(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hitta, "_DIAG_DIR", tmp_path)
    # Simulate a Cloudflare challenge page — recognizable signature
    cf_html = "<html><head><title>Just a moment...</title></head><body>cloudflare check</body></html>"
    resp = _FakeResp(cf_html)
    path = hitta._dump_empty_response("X", cf_html, resp)
    meta = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
    assert "Just a moment" in meta["html_head"]


# ----- E5: address-hash is deterministic (same input → same filename stem) -


def test_e5_address_hash_is_deterministic(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hitta, "_DIAG_DIR", tmp_path)
    resp1 = _FakeResp("<html>1</html>")
    resp2 = _FakeResp("<html>2</html>")

    # Different timestamp possible — but address hash should match
    p1 = hitta._dump_empty_response("Same Address", resp1.text, resp1)
    p2 = hitta._dump_empty_response("Same Address", resp2.text, resp2)

    # Filename format: <ts>_<addr-hash>.html → split on "_"
    hash1 = p1.stem.split("_")[1]
    hash2 = p2.stem.split("_")[1]
    assert hash1 == hash2


def test_e5_different_addresses_have_different_hashes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(hitta, "_DIAG_DIR", tmp_path)
    resp = _FakeResp("<html>x</html>")
    p1 = hitta._dump_empty_response("Address One", resp.text, resp)
    p2 = hitta._dump_empty_response("Address Two", resp.text, resp)
    assert p1.stem.split("_")[1] != p2.stem.split("_")[1]


# ----- E6: parse_hitta_html still works unchanged --------------------------


def test_e6_parse_hitta_html_unchanged_on_empty_ld() -> None:
    """Regression guard — adding diagnostic should not change parser behavior."""
    result = hitta.parse_hitta_html("<html><body>no JSON-LD here</body></html>", query="x")
    assert result.query == "x"
    assert result.contacts == []
    assert result.total_hits == 0


def test_e6_parse_hitta_html_with_real_ld_item() -> None:
    """Smoke: parser still extracts a Person from JSON-LD."""
    html = """
    <html><body>
    <script type="application/ld+json">
    {"@type": "Person", "name": "Edvin Pierre", "telephone": "+46-XXX-XXX-XX-XX"}
    </script>
    </body></html>
    """
    result = hitta.parse_hitta_html(html, query="Edvin")
    assert len(result.contacts) == 1
    assert result.contacts[0].kind == "person"
    assert result.contacts[0].name == "Edvin Pierre"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
