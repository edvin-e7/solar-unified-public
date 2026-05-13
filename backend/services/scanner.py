"""Unified scan pipeline — geocode → satellite → detection → persist.

Detection backend is selected by `DETECTION_BACKEND` env:
  unset           → legacy Gemini-via-prompts path (default, unchanged)
  ml|embed|gemini → new dispatcher in services.detection_model
  auto            → new dispatcher, picks first usable backend
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from prompts_loader import load, render

from services import atomic_fs, gemini, satellite
from services import geocode as geocode_mod

IMAGES_DIR = Path(__file__).parent.parent / "data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)


class ScanResult(TypedDict):
    address: str
    lat: float
    lng: float
    image_path: str
    has_panels: bool
    confidence: float
    panel_count_estimate: int
    roof_orientation: str
    roof_area_m2_estimate: int
    shading_risk: str
    reasoning: str
    scanned_at: str


async def scan_address(address: str) -> ScanResult:
    lat, lng = await geocode_mod.geocode(address)
    result = await scan_location(lat, lng, label=address, address=address)

    # Analytics: track scan-completion (silent on CH-down)
    try:
        from analytics import track
        # Extract region from address (last comma-separated token, common pattern)
        region = address.rsplit(",", 1)[-1].strip() if "," in address else None
        track(
            "prospect_scanned",
            subject_id=address,  # address acts as natural-key for prospect (DB also dedups)
            subject_type="prospect",
            region=region,
            has_panels=result.get("has_panels"),
            confidence=result.get("confidence"),
        )
    except Exception:
        # Analytics never blocks scan-pipeline
        pass

    return result


async def scan_location(lat: float, lng: float, *, label: str = "", address: str | None = None) -> ScanResult:
    image_bytes = await satellite.fetch_satellite_image(lat, lng)
    image_path = _save_image(image_bytes, label or f"{lat:.5f}_{lng:.5f}")
    addr_str = address or label or f"{lat:.5f},{lng:.5f}"
    rel_path = str(image_path.relative_to(IMAGES_DIR.parent))

    if os.getenv("DETECTION_BACKEND", "").strip().lower():
        return await _scan_via_dispatcher(image_bytes, lat, lng, addr_str, rel_path)

    # Default path: gemini.generate_json — but LLM_PROVIDER defaults to "ollama"
    # so this routes to the local Moondream model via Ollama (free).
    # Set LLM_PROVIDER=gemini + ALLOW_EXTERNAL_LLM=1 + GEMINI_API_KEY to use Gemini.
    prompt = render(load("detection"), {"address": addr_str, "lessons": ""})
    try:
        analysis = await gemini.generate_json(prompt, model="gemini-2.5-flash", image_bytes=image_bytes, phase="scanner-detection")
    except Exception as e:
        raise RuntimeError(f"Gemini detection failed: {e}") from e

    has_panels = bool(analysis.get("has_panels", False))
    confidence = max(0.0, min(1.0, _safe_float(analysis.get("confidence"))))
    panel_count = max(0, _safe_int(analysis.get("panel_count_estimate")))
    roof_area = max(0, _safe_int(analysis.get("roof_area_m2_estimate")))

    # Spec invariant I3: has_panels=True must agree with confidence + count.
    # Mirrors the same check in detection_gemini / detection_moondream.
    if has_panels and (confidence < 0.5 or panel_count < 1):
        has_panels = False

    return ScanResult(
        address=addr_str,
        lat=lat,
        lng=lng,
        image_path=rel_path,
        has_panels=has_panels,
        confidence=confidence,
        panel_count_estimate=panel_count,
        roof_orientation=str(analysis.get("roof_orientation", "unknown")),
        roof_area_m2_estimate=roof_area,
        shading_risk=str(analysis.get("shading_risk", "unknown")),
        reasoning=str(analysis.get("reasoning", "")),
        scanned_at=datetime.now(UTC).isoformat(),
    )


def _safe_float(v: object) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v: object) -> int:
    try:
        return int(float(v)) if v is not None else 0
    except (TypeError, ValueError):
        return 0


async def _scan_via_dispatcher(
    image_bytes: bytes, lat: float, lng: float, addr_str: str, rel_path: str
) -> ScanResult:
    from services import detection_escalate, detection_label_log

    # Active-learning wrapper: identical to detection_model.detect when
    # ESCALATE_ON_LOW_CONFIDENCE is unset; escalates borderline embed
    # verdicts to a teacher otherwise. See detection_escalate.py.
    result = await detection_escalate.detect(image_bytes, lat=lat, zoom=20)
    detection_label_log.record_inference(
        image_path=rel_path,
        backend=result["backend"],
        has_panels=result["has_panels"],
        confidence=result["confidence"],
        inference_ms=result["inference_ms"],
        address=addr_str,
    )
    panel_area = result.get("panel_area_m2") or 0.0
    roof_area = result.get("roof_area_m2") or 0.0
    return ScanResult(
        address=addr_str,
        lat=lat,
        lng=lng,
        image_path=rel_path,
        has_panels=result["has_panels"],
        confidence=result["confidence"],
        panel_count_estimate=int(panel_area / 1.6) if panel_area else 0,
        roof_orientation="unknown",
        roof_area_m2_estimate=int(roof_area),
        shading_risk="unknown",
        reasoning=f"backend={result['backend']} inference_ms={result['inference_ms']}",
        scanned_at=datetime.now(UTC).isoformat(),
    )


def _save_image(data: bytes, label: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label).strip("_")[:80]
    filename = f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = IMAGES_DIR / filename
    atomic_fs.write_bytes_atomic(path, data)
    return path


def save_history(results: list[ScanResult]) -> Path:
    history_dir = IMAGES_DIR.parent / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    atomic_fs.write_json_atomic(path, list(results))
    return path
