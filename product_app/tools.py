"""Custom tools for charts, reports, and infographic artifacts."""

from __future__ import annotations

import html
import io
import logging
import re
from datetime import datetime

from google.genai import types

try:  # pragma: no cover - optional import for test environments without ADK
    from google.adk.tools import ToolContext
except ModuleNotFoundError:  # pragma: no cover - fallback for pure helper tests
    class ToolContext:  # type: ignore[override]
        pass

try:  # pragma: no cover - optional import for slim test environments
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ModuleNotFoundError:  # pragma: no cover - fallback path handled in _build_pdf_report
    colors = LETTER = ParagraphStyle = getSampleStyleSheet = inch = Paragraph = None
    SimpleDocTemplate = Spacer = None

from .artifact_storage import upload_artifact
from .config import load_settings

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Convert a string to a URL-friendly slug."""
    normalized = value.strip().lower()
    normalized = _SLUG_PATTERN.sub("-", normalized).strip("-")
    return normalized or "artifact"

logger = logging.getLogger(__name__)
settings = load_settings()
OUTPUTS_DIR = settings.output_dir

# ── Report title mapping ────────────────────────────────────────────

_REPORT_TITLES: dict[str, tuple[str, str]] = {
    "deploy_product": ("MVP Deployment Report", "Reporte de Despliegue MVP"),
}

_REPORT_SUBTITLES: dict[str, tuple[str, str]] = {
    "deploy_product": ("Product Deployment Summary", "Resumen de Despliegue de Producto"),
}


def _get_report_title(research_style: str, language: str = "en") -> str:
    """Return the report title for a given research style and language."""
    titles = _REPORT_TITLES.get(research_style, ("Research Report", "Reporte de Investigacion"))
    return titles[1] if language == "es" else titles[0]


def _get_report_subtitle(research_style: str, language: str = "en") -> str:
    """Return the report subtitle for a given research style and language."""
    subtitles = _REPORT_SUBTITLES.get(research_style, ("Research Brief", "Resumen de Investigacion"))
    return subtitles[1] if language == "es" else subtitles[0]


def _build_part(payload: bytes, mime_type: str) -> types.Part:
    return types.Part(inline_data=types.Blob(data=payload, mime_type=mime_type))


async def _persist_artifact(
    filename: str,
    payload: bytes,
    mime_type: str,
    tool_context: ToolContext,
) -> dict:
    local_path = OUTPUTS_DIR / filename
    local_path.write_bytes(payload)

    version = None
    try:
        version = await tool_context.save_artifact(
            filename=filename,
            artifact=_build_part(payload, mime_type),
        )
    except ValueError:
        logger.warning("Artifact service not configured. Saved only to local disk.")
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Artifact save to ADK failed: %s", exc)

    response = {
        "artifact": filename,
        "local_path": str(local_path),
        "mime_type": mime_type,
    }
    gcs_artifact = None
    try:
        gcs_artifact = upload_artifact(filename, payload, mime_type)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("Artifact upload to GCS failed: %s", exc)

    if gcs_artifact is not None:
        response["gcs_bucket"] = gcs_artifact.bucket
        response["gcs_object"] = gcs_artifact.object_name
    if version is not None:
        response["version"] = version
    return response


def _with_bold(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)


def _with_pdf_bold(text: str) -> str:
    escaped = html.escape(text)
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)


def render_markdown_like_html(markdown_text: str) -> str:
    sections: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            sections.append("</ul>")
            in_list = False

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            continue

        if line.startswith("## "):
            close_list()
            sections.append(f"<h2>{_with_bold(line[3:])}</h2>")
            continue

        if line.startswith("### "):
            close_list()
            sections.append(f"<h3>{_with_bold(line[4:])}</h3>")
            continue

        if line.startswith("- "):
            if not in_list:
                sections.append("<ul>")
                in_list = True
            sections.append(f"<li>{_with_bold(line[2:])}</li>")
            continue

        close_list()
        sections.append(f"<p>{_with_bold(line)}</p>")

    close_list()
    return "\n".join(sections)


def _wrap_svg_text(value: str, *, width: int = 24) -> list[str]:
    words = value.split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _build_pdf_report(report_data: str, current_date: str, title: str = "Research Report") -> bytes:
    if SimpleDocTemplate is None:
        body = (
            "%PDF-1.4\n"
            "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
            "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
            f"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 72 720 Td ({current_date}) Tj ET\nendstream endobj\n"
            "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
            "xref\n0 6\n0000000000 65535 f \n"
            "0000000010 00000 n \n0000000053 00000 n \n0000000112 00000 n \n0000000240 00000 n \n0000000346 00000 n \n"
            "trailer<</Size 6/Root 1 0 R>>\nstartxref\n416\n%%EOF"
        )
        return body.encode("ascii")

    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title=title,
        author="Product Name",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#16385c"),
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#5a6678"),
        spaceAfter=18,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#16385c"),
        spaceBefore=14,
        spaceAfter=8,
    )
    subheading_style = ParagraphStyle(
        "ReportSubheading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#40586f"),
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#1f3045"),
        spaceAfter=8,
    )
    bullet_style = ParagraphStyle(
        "ReportBullet",
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
    )

    story = [
        Paragraph(html.escape(title), title_style),
        Paragraph(f"Generated on {html.escape(current_date)}", meta_style),
    ]

    for raw_line in report_data.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 0.08 * inch))
            continue

        if line.startswith("## "):
            story.append(Paragraph(_with_pdf_bold(line[3:]), heading_style))
            continue

        if line.startswith("### "):
            story.append(Paragraph(_with_pdf_bold(line[4:]), subheading_style))
            continue

        if line.startswith("- "):
            story.append(Paragraph(f"&bull; {_with_pdf_bold(line[2:])}", bullet_style))
            continue

        story.append(Paragraph(_with_pdf_bold(line), body_style))

    document.build(story)
    buffer.seek(0)
    return buffer.read()


async def generate_html_report(report_data: str, tool_context: ToolContext) -> dict:
    """Render a polished HTML report from the investor memo text."""

    current_date = datetime.now().strftime("%B %d, %Y")
    body_html = render_markdown_like_html(report_data)

    # Extract research style and language from session state
    _state = getattr(tool_context, "state", {}) or {}
    _style_key = _state.get("research_style", "deploy_product")
    _lang = _state.get("language", "en")
    _title = _get_report_title(_style_key, _lang)
    _subtitle = _get_report_subtitle(_style_key, _lang)

    html_document = f"""<!DOCTYPE html>
<html lang="{html.escape(_lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(_title)}</title>
  <style>
    :root {{
      --ink: #11263f;
      --ink-soft: #40586f;
      --accent: #c9a227;
      --paper: #f6f3eb;
      --panel: #ffffff;
      --border: #d7dde4;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top right, rgba(201, 162, 39, 0.16), transparent 24%),
        linear-gradient(180deg, #f8f7f2 0%, #eef1f5 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 40px 20px 56px;
    }}
    .hero {{
      background: linear-gradient(135deg, #183554, #0b1c2d);
      color: white;
      border-radius: 24px;
      padding: 28px 30px;
      box-shadow: 0 20px 45px rgba(15, 27, 43, 0.14);
      margin-bottom: 28px;
    }}
    .hero p {{
      margin: 0 0 8px;
      color: rgba(255, 255, 255, 0.86);
      letter-spacing: 0.06em;
      text-transform: uppercase;
      font-size: 12px;
    }}
    .hero h1 {{
      margin: 0;
      font-size: 34px;
      line-height: 1.08;
    }}
    .report {{
      background: var(--panel);
      border-radius: 22px;
      padding: 30px;
      border: 1px solid var(--border);
      box-shadow: 0 16px 34px rgba(15, 27, 43, 0.08);
    }}
    h2 {{
      margin-top: 28px;
      margin-bottom: 12px;
      padding-bottom: 8px;
      font-size: 22px;
      border-bottom: 2px solid rgba(201, 162, 39, 0.5);
    }}
    h3 {{
      margin-top: 20px;
      margin-bottom: 8px;
      font-size: 18px;
      color: var(--ink-soft);
    }}
    p, li {{
      font-size: 16px;
      line-height: 1.7;
    }}
    ul {{
      margin-top: 8px;
      padding-left: 22px;
    }}
    .footer {{
      margin-top: 24px;
      font-size: 12px;
      color: var(--ink-soft);
      text-align: right;
    }}
    @media print {{
      body {{ background: white; }}
      .hero, .report {{ box-shadow: none; }}
      main {{ padding: 0; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <p>{html.escape(_subtitle)}</p>
      <h1>{html.escape(_title)}</h1>
      <p>Date: {html.escape(current_date)}</p>
    </section>
    <section class="report">
      {body_html}
      <div class="footer">Generated by Product Name</div>
    </section>
  </main>
</body>
</html>
"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    _slug = _style_key.replace(" ", "_")
    html_filename = f"{_slug}_report_{timestamp}.html"
    saved_html = await _persist_artifact(
        html_filename,
        html_document.encode("utf-8"),
        "text/html",
        tool_context,
    )
    pdf_filename = f"{_slug}_report_{timestamp}.pdf"
    pdf_payload = _build_pdf_report(report_data, current_date, title=_title)
    saved_pdf = await _persist_artifact(
        pdf_filename,
        pdf_payload,
        "application/pdf",
        tool_context,
    )

    return {
        "status": "success",
        "message": f"HTML and PDF {_title} generated successfully.",
        "html_report": saved_html,
        "pdf_report": saved_pdf,
        **saved_html,
    }


async def generate_infographic(
    company_name: str,
    tool_context: ToolContext,
    investment_stage: str = "Unknown",
    founded: str = "Unknown",
    headquarters: str = "Unknown",
    funding_status: str = "Unknown",
    market_size: str = "Unknown",
    growth_rate: str = "Unknown",
    risk_score: str = "Unknown",
    recommendation: str = "Unknown",
) -> dict:
    """Create a local SVG infographic from structured company summary data."""

    if not settings.infographic_enabled:
        return {
            "status": "skipped",
            "message": "Infographic generation is disabled by configuration.",
        }

    card_values = [
        ("Stage", investment_stage),
        ("Founded", founded),
        ("HQ", headquarters),
        ("Funding", funding_status),
        ("Market", market_size),
        ("Growth", growth_rate),
        ("Risk", risk_score),
        ("Recommendation", recommendation),
    ]

    card_positions = [
        (50, 180),
        (360, 180),
        (670, 180),
        (980, 180),
        (50, 400),
        (360, 400),
        (670, 400),
        (980, 400),
    ]

    cards_svg: list[str] = []
    for (title, value), (x, y) in zip(card_values, card_positions):
        lines = _wrap_svg_text(value, width=22)
        tspans = []
        for index, line in enumerate(lines[:3]):
            y_position = 86 + (index * 30)
            tspans.append(
                f'<tspan x="26" y="{y_position}">{html.escape(line)}</tspan>'
            )
        cards_svg.append(
            f"""
  <g transform="translate({x},{y})">
    <rect width="260" height="170" rx="24" fill="#ffffff" stroke="#d2dae4"/>
    <text x="26" y="42" font-family="Georgia, serif" font-size="18" fill="#53667a">{html.escape(title)}</text>
    <text font-family="Georgia, serif" font-size="28" font-weight="700" fill="#132f4f">
      {''.join(tspans)}
    </text>
  </g>
"""
        )

    svg_document = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" viewBox="0 0 1280 760">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f9f3e4"/>
      <stop offset="55%" stop-color="#f2f5f8"/>
      <stop offset="100%" stop-color="#e6edf4"/>
    </linearGradient>
    <linearGradient id="hero" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#173555"/>
      <stop offset="100%" stop-color="#0e2034"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="760" fill="url(#bg)"/>
  <rect x="42" y="34" width="1196" height="116" rx="30" fill="url(#hero)"/>
  <text x="82" y="82" font-family="Georgia, serif" font-size="22" fill="#d9b34a">MVP FACTORY SNAPSHOT</text>
  <text x="82" y="126" font-family="Georgia, serif" font-size="42" font-weight="700" fill="#ffffff">{html.escape(company_name)}</text>
  {''.join(cards_svg)}
</svg>
"""

    filename = f"{slugify(company_name)}_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg"
    saved = await _persist_artifact(
        filename,
        svg_document.encode("utf-8"),
        "image/svg+xml",
        tool_context,
    )

    return {
        "status": "success",
        "message": "Infographic generated successfully.",
        **saved,
    }
