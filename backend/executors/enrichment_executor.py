"""EnrichmentExecutor — hitta fetch-first with strict empty/block distinction.

Empty results and network blocks are distinct failure modes and must NOT be
logged as `passed`. Downstream learning depends on this signal — if silent
empties count as success, the outcome journal becomes useless for signal and
the improvement suggester repeats doomed approaches.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from learning_journal import record
from services import hitta
from services.hitta import HittaBlocked, HittaContact, HittaEmpty, HittaResult


class EnrichmentExecutor:
    name = "enrichment_executor"

    async def enrich_address(self, address: str) -> dict[str, Any]:
        try:
            result = await hitta.lookup_hitta(address)
        except HittaEmpty as exc:
            record(
                phase="enrichment",
                outcome="failed",
                lesson=f"hitta empty for {address}",
                error=str(exc),
                metadata={"failure_kind": "empty", "address": address},
            )
            return _failure_payload(address, kind="empty", message=str(exc))
        except HittaBlocked as exc:
            record(
                phase="enrichment",
                outcome="failed",
                lesson=f"hitta blocked/unreachable for {address}",
                error=str(exc),
                metadata={"failure_kind": "blocked", "address": address},
            )
            return _failure_payload(address, kind="blocked", message=str(exc))

        best_person = result.best_person()
        best_contact = result.best_contact()
        record(
            phase="enrichment",
            outcome="passed",
            lesson=f"hitta enriched {address}: {len(result.contacts)} contacts, person={bool(best_person)}",
            metadata={
                "total_hits": result.total_hits,
                "contacts": len(result.contacts),
                "person_found": bool(best_person),
                "address": address,
            },
        )
        return {
            "address": address,
            "source": "hitta",
            "total_hits": result.total_hits,
            "contacts": [_contact_dict(c) for c in result.contacts],
            "best_contact": _contact_dict(best_contact) if best_contact else None,
            "best_person": _contact_dict(best_person) if best_person else None,
        }

    async def enrich_batch(self, addresses: list[str]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        person_hits = 0
        contact_hits = 0
        failures: dict[str, int] = {"empty": 0, "blocked": 0}

        for addr in addresses:
            result = await self.enrich_address(addr)
            results.append(result)
            if result.get("failure_kind"):
                failures[result["failure_kind"]] = failures.get(result["failure_kind"], 0) + 1
                continue
            if result.get("best_person"):
                person_hits += 1
            if result.get("best_contact"):
                contact_hits += 1

        total = len(addresses)
        record(
            phase="enrichment",
            outcome="passed" if person_hits + contact_hits > 0 else "failed",
            lesson=(
                f"batch enrich {total}: person={person_hits}, contact={contact_hits}, "
                f"empty={failures.get('empty', 0)}, blocked={failures.get('blocked', 0)}"
            ),
            metadata={
                "total": total,
                "person_hits": person_hits,
                "contact_hits": contact_hits,
                "failures": failures,
            },
        )
        return {
            "total": total,
            "person_hits": person_hits,
            "contact_hits": contact_hits,
            "failures": failures,
            "results": results,
        }


def _failure_payload(address: str, *, kind: str, message: str) -> dict[str, Any]:
    return {
        "address": address,
        "source": "hitta",
        "failure_kind": kind,
        "error": message,
        "total_hits": 0,
        "contacts": [],
        "best_contact": None,
        "best_person": None,
    }


def _contact_dict(c: HittaContact) -> dict[str, Any]:
    d = asdict(c)
    return d


def _ensure_typed(result: HittaResult) -> HittaResult:
    return result
