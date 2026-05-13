"""Enrichment endpoints — hitta fetch-first server-side.

Per-person contact data (name/phone/age) comes from whatever hitta.se exposes
publicly (mostly businesses + some published individuals). Deeper per-resident
lookups require the Electron renderer (mrkoll/birthday — Cloudflare-blocked
for backend). Every returned contact is scored against the requested address
via `services.address_match`, so downstream can't confuse a same-city hit for
an exact match. See specs/enrich_person.md.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from services import address_match, hitta
from services.address_match import MatchResult, NormalizedAddress
from services.hitta import HittaBlocked, HittaContact, HittaEmpty, HittaResult

router = APIRouter()

_MIN_CONFIDENCE_SCORE = 0.2


class EnrichRequest(BaseModel):
    address: str = Field(min_length=3, max_length=200)
    name: str | None = None


class EnrichPersonResponse(BaseModel):
    name: str | None
    age: int | None
    phone: str | None
    source: str
    contacts: list[dict]
    total_hits: int
    match: dict


@router.post("/person", response_model=EnrichPersonResponse)
async def enrich_person(req: EnrichRequest) -> EnrichPersonResponse:
    if not req.address.strip():
        raise HTTPException(status_code=422, detail="address must not be whitespace-only")

    result = await _lookup_or_raise(req.address)
    requested = address_match.normalize(req.address)
    scored = _score_and_sort(result.contacts, requested)

    if not scored or scored[0][1].score < _MIN_CONFIDENCE_SCORE:
        raise HTTPException(
            status_code=404,
            detail=f"no hitta contacts within same city for {req.address!r}",
        )

    best_contact, best_match = _pick_best(scored, preferred_name=req.name)
    return EnrichPersonResponse(
        name=best_contact.name if best_contact else None,
        age=None,
        phone=best_contact.telephone if best_contact else None,
        source="hitta",
        contacts=[_contact_dict(c, m) for c, m in scored],
        total_hits=result.total_hits or len(scored),
        match=_match_block(req.address, requested, best_match),
    )


class BatchEnrichRequest(BaseModel):
    addresses: list[str]


@router.post("/batch")
async def enrich_batch(req: BatchEnrichRequest) -> dict:
    results: list[dict] = []
    errors: list[dict] = []
    for addr in req.addresses[:50]:
        try:
            result = await hitta.lookup_hitta(addr)
        except (HittaBlocked, HittaEmpty) as exc:
            errors.append({"address": addr, "error_kind": type(exc).__name__, "error": str(exc)})
            continue
        requested = address_match.normalize(addr)
        scored = _score_and_sort(result.contacts, requested)
        if not scored or scored[0][1].score < _MIN_CONFIDENCE_SCORE:
            errors.append({"address": addr, "error_kind": "NoConfidentMatch", "error": "max score < 0.2"})
            continue
        best_contact, best_match = _pick_best(scored)
        results.append(
            {
                "address": addr,
                "name": best_contact.name if best_contact else None,
                "phone": best_contact.telephone if best_contact else None,
                "total_hits": result.total_hits or len(scored),
                "contacts": [_contact_dict(c, m) for c, m in scored],
                "match": _match_block(addr, requested, best_match),
            }
        )
    return {"results": results, "errors": errors, "count": len(results)}


async def _lookup_or_raise(address: str) -> HittaResult:
    try:
        return await hitta.lookup_hitta(address)
    except HittaBlocked as exc:
        raise HTTPException(status_code=502, detail=f"hitta blocked/unreachable: {exc}") from exc
    except HittaEmpty as exc:
        raise HTTPException(status_code=404, detail=f"no hitta contacts: {exc}") from exc


def _score_and_sort(
    contacts: list[HittaContact], requested: NormalizedAddress
) -> list[tuple[HittaContact, MatchResult]]:
    """Score every contact, sort by score desc then name asc (stable tiebreak)."""
    scored = [(c, address_match.score(requested, _normalize_contact(c))) for c in contacts]
    scored.sort(key=lambda pair: (-pair[1].score, pair[0].name.lower()))
    return scored


def _normalize_contact(c: HittaContact) -> NormalizedAddress:
    parts = " ".join(p for p in (c.street_address, c.postal_code, c.city) if p)
    return address_match.normalize(parts)


def _pick_best(
    scored: list[tuple[HittaContact, MatchResult]],
    preferred_name: str | None = None,
) -> tuple[HittaContact | None, MatchResult | None]:
    if preferred_name:
        needle = preferred_name.strip().lower()
        if needle:
            for c, m in scored:
                if needle in c.name.lower():
                    return c, m
    return (scored[0] if scored else (None, None))


def _match_block(
    requested_raw: str, requested: NormalizedAddress, best: MatchResult | None
) -> dict:
    return {
        "requested": requested_raw,
        "normalized": {
            "street": requested.street,
            "number": requested.number,
            "postal": requested.postal,
            "city": requested.city,
        },
        "best_score": best.score if best else 0.0,
        "best_kind": best.kind if best else "none",
        "confidence_label": best.label if best else "inget",
    }


def _contact_dict(c: HittaContact, match: MatchResult) -> dict:
    return {
        "kind": c.kind,
        "name": c.name,
        "telephone": c.telephone,
        "street_address": c.street_address,
        "postal_code": c.postal_code,
        "city": c.city,
        "url": c.url,
        "lat": c.lat,
        "lng": c.lng,
        "match_score": match.score,
        "match_kind": match.kind,
        "confidence_label": match.label,
    }
