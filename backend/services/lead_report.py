"""Lead-report PDF generator for solar-installer deliveries.

Produces a 1-2 page PDF with:
- Cover: region, snapshot date, lead-count, value-prop
- Lead table: address, score, panel-status, contact
- Methodology footer: data sources, refresh frequency

Reportlab pure-Python — no wkhtmltopdf locale-issues, no pandoc dep.
"""

from __future__ import annotations

import io
from collections.abc import Iterable
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Solar Almanac-inspired palette — paper + ink + amber for accents
_PAPER = colors.HexColor("#F5F0E6")
_INK = colors.HexColor("#1F1814")
_INK_60 = colors.HexColor("#5C5246")
_AMBER = colors.HexColor("#C8741A")
_RULE = colors.HexColor("#D1C5AE")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], textColor=_INK,
            fontName="Helvetica-Bold", fontSize=24, spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"], textColor=_AMBER,
            fontName="Helvetica", fontSize=11, spaceAfter=18,
            textTransform="uppercase",
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], textColor=_INK,
            fontName="Helvetica-Bold", fontSize=14, spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], textColor=_INK,
            fontName="Helvetica", fontSize=10, leading=14, spaceAfter=6,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], textColor=_INK_60,
            fontName="Helvetica", fontSize=8, leading=11,
        ),
    }


def build_lead_report(
    *,
    region: str,
    installer_name: str | None = None,
    leads: Iterable[dict],
    generated_at: datetime | None = None,
) -> bytes:
    """Build a PDF for installer-delivery. Returns the rendered bytes.

    Args:
        region: Display label (e.g. "Sollentuna").
        installer_name: Personalize to recipient (e.g. "Solfasaden AB"). None → generic.
        leads: Iterable of dicts with keys: address, score, has_panels, panel_confidence,
            annual_kwh, owner_name (optional).
        generated_at: Override for tests; defaults to now (UTC).

    Notes:
        - Owner-data filtering happens upstream (GDPR-light export, etc.) — this
          function renders whatever is in the dict.
        - Layout breaks pages automatically when lead-count > ~20.
    """
    generated_at = generated_at or datetime.now(UTC)
    leads_list = list(leads)
    styles = _styles()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Solar Leads — {region}",
        author="Solar Unified",
    )

    story: list = []
    title_to = f" — {installer_name}" if installer_name else ""
    story.append(Paragraph(f"Solar Leads · {region}{title_to}", styles["title"]))
    story.append(Paragraph(
        f"Genererad {generated_at:%Y-%m-%d %H:%M UTC}  ·  {len(leads_list)} prospekt",
        styles["subtitle"],
    ))

    # Intro
    story.append(Paragraph(
        f"Översikt av <b>{len(leads_list)} byggnader</b> i {region} med detection-data "
        f"från lokal AI-vision (Moondream) mot ArcGIS-satellitbilder. Geokod via "
        f"Nominatim (OpenStreetMap). Inga betalda API:er — leveransen är 100% "
        f"kostnadsfri på vår sida.",
        styles["body"],
    ))

    # Lead table
    story.append(Paragraph("Lead-tabell", styles["h2"]))

    header = ["#", "Adress", "Score", "Paneler", "Konf.", "kWh/år"]
    rows: list[list] = [header]
    for idx, lead in enumerate(leads_list, 1):
        has_panels = lead.get("has_panels")
        panels_label = "Ja" if has_panels else ("Nej" if has_panels is False else "—")
        score = lead.get("score")
        score_label = f"{float(score):.2f}" if score is not None else "—"
        conf = lead.get("panel_confidence")
        conf_label = f"{float(conf) * 100:.0f}%" if conf is not None else "—"
        kwh = lead.get("annual_kwh")
        kwh_label = f"{round(float(kwh)):,}".replace(",", " ") if kwh else "—"
        addr = str(lead.get("address", ""))[:70]
        rows.append([str(idx), addr, score_label, panels_label, conf_label, kwh_label])

    table = Table(
        rows,
        colWidths=[1 * cm, 8 * cm, 1.7 * cm, 1.8 * cm, 1.7 * cm, 2.3 * cm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), _PAPER),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "LEFT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_PAPER, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.25, _RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)

    # Footer
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Metod + Källor", styles["h2"]))
    story.append(Paragraph(
        "Byggnadsdata hämtas via Overpass API (OpenStreetMap), geokod via Nominatim, "
        "satellitbilder från ArcGIS World Imagery. Paneldetektion sker via Moondream "
        "(lokal vision-modell). Alla källor är kostnadsfria och GDPR-vänliga — ingen "
        "data lämnar svensk/europeisk infrastruktur.",
        styles["caption"],
    ))
    story.append(Paragraph(
        "Färskhets-tip: be om en re-snapshot innan kampanj-launch — buildings + "
        "ägardata förändras kontinuerligt. Standard-leverans är max 30 dagar gammal.",
        styles["caption"],
    ))

    doc.build(story)
    return buf.getvalue()
