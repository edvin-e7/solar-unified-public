"""Mrkoll.se HTML parser — pure function.

Ported from edvin-solar-master/src/core/scraper.py:_parse_mrkoll_html.

Mrkoll.se is Cloudflare-protected and must be fetched via the Electron renderer
(AGENTS.md — Cloudflare-blocked for backend httpx). This module holds the parsing
logic only. The fetcher — whether Electron or a backend Playwright fallback —
feeds HTML into `parse_mrkoll_html`.

Extracted fields (per master's parser contract):
    name, age, address, postal_code, city, phone, mobile, income, property_value
"""

from __future__ import annotations

import contextlib
import re
from typing import Any


def parse_mrkoll_html(html: str) -> dict[str, Any]:
    """Extract structured person fields from a mrkoll.se person page.

    Returns a dict with only the fields that were present in the HTML. Missing
    fields are omitted (not set to None/empty) so callers can distinguish
    "not found" from "found but empty". Matches EnrichmentExecutor._extract_person_fields
    expectations.
    """
    out: dict[str, Any] = {}

    name_match = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
    if name_match:
        name = name_match.group(1).strip()
        if name:
            out["name"] = name

    age_match = re.search(r"(\d{1,3})\s*(?:år|ar)", html)
    if age_match:
        age = int(age_match.group(1))
        if 0 < age < 120:
            out["age"] = age

    addr_match = re.search(
        r"([\wÅÄÖåäö\s]+(?:gatan|vägen|gränd|allé|stigen|torget|plats)\s+\d+[A-Za-z]?)",
        html,
        re.IGNORECASE,
    )
    if addr_match:
        out["address"] = addr_match.group(1).strip()

    postal_match = re.search(r"(\d{3}\s?\d{2})\s+([\wÅÄÖåäö]+)", html)
    if postal_match:
        out["postal_code"] = postal_match.group(1)
        out["city"] = postal_match.group(2)

    phones = re.findall(r"(?:0\d{1,3}[-\s]?\d{2,3}[-\s]?\d{2,4}[-\s]?\d{2,4})", html)
    for ph in phones:
        cleaned = ph.strip()
        if cleaned.startswith("07"):
            out.setdefault("mobile", cleaned)
        else:
            out.setdefault("phone", cleaned)

    income_match = re.search(
        r"(?:inkomst|taxerad)[^<]*?(\d[\d\s]{2,10})\s*(?:kr|SEK)",
        html,
        re.IGNORECASE,
    )
    if income_match:
        income_str = income_match.group(1).replace(" ", "").replace("\xa0", "")
        with contextlib.suppress(ValueError):
            out["income"] = int(income_str)

    prop_match = re.search(
        r"(?:taxeringsv|fastighetsv)[^<]*?(\d[\d\s]{2,12})\s*(?:kr|SEK)",
        html,
        re.IGNORECASE,
    )
    if prop_match:
        prop_str = prop_match.group(1).replace(" ", "").replace("\xa0", "")
        with contextlib.suppress(ValueError):
            out["property_value"] = int(prop_str)

    return out
