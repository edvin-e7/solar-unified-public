"""Fetch-first Swedish registry lookup — hitta.se reverse-address.

Strategy: parse the page's own structured data — schema.org JSON-LD blocks and the
Next.js `__NEXT_DATA__` state — instead of fragile CSS selectors. Both are stable
server-rendered contracts that survive DOM refactors.

Split into fetch (`lookup_hitta`) and parse (`parse_hitta_html`) so the parser
is unit-testable against committed HTML fixtures without hitting the live site.

Person-level data (name/phone/PN for individuals) still requires mrkoll/birthday,
which run in the Electron renderer because of Cloudflare. Hitta exposes mostly
businesses + a small number of published individuals for free.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

_log = logging.getLogger(__name__)

# Diagnostic dump dir for HittaEmpty payloads — backend/data/ is gitignored per
# CLAUDE.md rule 10 (PII first-class). Set HITTA_DIAGNOSTIC_DIR to override or
# empty-string to disable dumping (default is enabled to break the Bug 1
# black-box-on-HittaEmpty diagnosis loop).
_DEFAULT_DIAG_DIR = Path(__file__).parent.parent / "data" / "hitta_diagnostics"
_DIAG_DIR_ENV = os.getenv("HITTA_DIAGNOSTIC_DIR")
_DIAG_DIR: Path | None = (
    Path(_DIAG_DIR_ENV) if _DIAG_DIR_ENV is not None and _DIAG_DIR_ENV.strip() else _DEFAULT_DIAG_DIR
) if _DIAG_DIR_ENV != "" else None


def _dump_empty_response(address: str, html: str, response: httpx.Response) -> Path | None:
    """Dump raw response on HittaEmpty so the next session can diagnose root cause.

    Writes to backend/data/hitta_diagnostics/<ts>_<addr-hash>.html + .meta.json
    (gitignored). Returns the dump path on success, None if disabled or on
    failure (failure must NOT block the HittaEmpty raise — diagnostic best-effort).

    PII consideration: address goes into filename hash only, not plaintext. HTML
    body is raw and may contain PII — that's intentional, the dump dir is
    gitignored and exists explicitly for ops diagnosis.
    """
    if _DIAG_DIR is None:
        return None
    try:
        _DIAG_DIR.mkdir(parents=True, exist_ok=True)
        addr_hash = hashlib.sha256(address.encode("utf-8")).hexdigest()[:12]
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        stem = f"{ts}_{addr_hash}"
        html_path = _DIAG_DIR / f"{stem}.html"
        meta_path = _DIAG_DIR / f"{stem}.meta.json"
        html_path.write_text(html, encoding="utf-8")
        meta_path.write_text(
            json.dumps(
                {
                    "address_hash": addr_hash,
                    "ts": ts,
                    "status_code": response.status_code,
                    "html_length": len(html),
                    "html_head": html[:200],
                    "url": str(response.url),
                    "content_type": response.headers.get("content-type"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return html_path
    except Exception as exc:  # noqa: BLE001 -- best-effort diagnostic
        _log.warning("hitta diagnostic dump failed: %s", exc)
        return None


UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0 Safari/537.36"
)


class HittaError(Exception):
    """Base hitta error."""


class HittaBlocked(HittaError):
    """Hitta returned non-200, challenge page, or network failure."""


class HittaEmpty(HittaError):
    """Hitta returned 200 but zero parseable contacts."""


@dataclass(slots=True)
class HittaContact:
    kind: str  # "business" | "person"
    name: str
    telephone: str | None = None
    street_address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    url: str | None = None
    lat: float | None = None
    lng: float | None = None


@dataclass(slots=True)
class HittaResult:
    query: str
    contacts: list[HittaContact] = field(default_factory=list)
    total_hits: int = 0
    tabs: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "contacts": [asdict(c) for c in self.contacts],
            "total_hits": self.total_hits,
            "tabs": self.tabs,
        }

    def best_person(self) -> HittaContact | None:
        for c in self.contacts:
            if c.kind == "person":
                return c
        return None

    def best_contact(self) -> HittaContact | None:
        return self.best_person() or (self.contacts[0] if self.contacts else None)


async def lookup_hitta(address: str) -> HittaResult:
    """Query hitta.se reverse-address lookup and return structured contacts.

    Raises:
        HittaBlocked: network error, non-200, or challenge page.
        HittaEmpty: 200 OK but no contacts parseable from response.
    """
    url = "https://www.hitta.se/sök"
    try:
        async with httpx.AsyncClient(
            timeout=12, headers={"User-Agent": UA}, follow_redirects=True
        ) as client:
            response = await client.get(url, params={"vad": address})
    except httpx.HTTPError as exc:
        raise HittaBlocked(f"network error for {address!r}: {exc}") from exc

    if response.status_code != 200:
        raise HittaBlocked(f"HTTP {response.status_code} for {address!r}")

    result = parse_hitta_html(response.text, query=address)
    if not result.contacts:
        # Diagnostic dump — best-effort, must not block the raise.
        dump_path = _dump_empty_response(address, response.text, response)
        suffix = f" (diagnostic: {dump_path})" if dump_path else ""
        _log.info(
            "HittaEmpty for %r — html_len=%d head=%r%s",
            address,
            len(response.text),
            response.text[:200].replace("\n", "\\n"),
            suffix,
        )
        raise HittaEmpty(f"hitta returned 200 but zero contacts for {address!r}{suffix}")
    return result


def parse_hitta_html(html: str, query: str) -> HittaResult:
    """Pure parser — extract contacts from hitta.se server-rendered HTML.

    Safe to call with fixture HTML — does not hit network.
    """
    soup = BeautifulSoup(html, "lxml")
    result = HittaResult(query=query)

    for script in soup.find_all("script", type="application/ld+json"):
        payload = script.string or script.get_text()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        _collect_ld_contacts(data, result)

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data and (next_data.string or next_data.get_text()):
        try:
            nd = json.loads(next_data.string or next_data.get_text())
            _collect_tabs_from_next_data(nd, result)
        except json.JSONDecodeError:
            pass

    return result


def _collect_ld_contacts(data: Any, result: HittaResult) -> None:
    if isinstance(data, list):
        for item in data:
            _collect_ld_contacts(item, result)
        return
    if not isinstance(data, dict):
        return

    if data.get("@type") == "ItemList":
        items = data.get("itemListElement") or []
        for entry in items:
            if not isinstance(entry, dict):
                continue
            # Two shapes observed in production (2026-05-13):
            #   Nested:  {@type: ListItem, position, item: {type, name, address, ...}}
            #   Flat:    {@type: ListItem, position, name, url}  ← no `item` key
            # Stockholm queries tend to return Nested. Malmö + Göteborg often
            # return Flat (root-cause of docs/BUGS.md Bug 1 — 67% empty rate).
            item = entry.get("item")
            if isinstance(item, dict):
                contact = _contact_from_ld_item(item)
            else:
                # Flat shape — entry IS the listing
                contact = _contact_from_ld_item(entry)
            if contact:
                result.contacts.append(contact)
        num = data.get("numberOfItems")
        if isinstance(num, int):
            result.total_hits = max(result.total_hits, num)
        return

    if _is_contactable_type(data):
        contact = _contact_from_ld_item(data)
        if contact:
            result.contacts.append(contact)


def _is_contactable_type(item: dict) -> bool:
    type_ = item.get("@type") or item.get("type") or ""
    if isinstance(type_, list):
        type_ = " ".join(str(t) for t in type_)
    return any(kw in type_ for kw in ("Person", "LocalBusiness", "Organization"))


def _contact_from_ld_item(item: dict | None) -> HittaContact | None:
    if not isinstance(item, dict):
        return None
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return None

    type_ = item.get("@type") or item.get("type") or ""
    if isinstance(type_, list):
        type_ = " ".join(str(t) for t in type_)
    kind = "person" if "Person" in type_ else "business"

    addr = item.get("address") if isinstance(item.get("address"), dict) else {}
    geo = item.get("geo") if isinstance(item.get("geo"), dict) else {}

    return HittaContact(
        kind=kind,
        name=name.strip(),
        telephone=_clean_str(item.get("telephone")),
        street_address=_clean_str(addr.get("streetAddress")),
        postal_code=_clean_str(addr.get("postalCode")),
        city=_clean_str(addr.get("addressLocality")),
        url=_clean_str(item.get("url")),
        lat=_safe_float(geo.get("latitude")),
        lng=_safe_float(geo.get("longitude")),
    )


def _collect_tabs_from_next_data(nd: dict, result: HittaResult) -> None:
    page_props = nd.get("props", {}).get("pageProps", {}) if isinstance(nd, dict) else {}
    tabs = page_props.get("resultTabs")
    if not isinstance(tabs, list):
        return
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        name = tab.get("name") or tab.get("type") or tab.get("id")
        count = tab.get("count") or tab.get("total") or tab.get("numberOfItems")
        if name and isinstance(count, int):
            result.tabs[str(name)] = count


def _clean_str(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s or None


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
