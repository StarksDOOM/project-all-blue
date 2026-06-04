"""
Phase 5 — isolated PDF compilation from legal contract markdown/HTML text.

Uses ReportLab (no system GTK deps) for portable Windows/Linux rendering.
"""

from __future__ import annotations

import hashlib
import logging
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

logger = logging.getLogger(__name__)

SECURE_PDF_DIR = Path(__file__).resolve().parents[1] / "storage" / "secure_pdfs"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _markdown_to_flowables(markdown_text: str, styles) -> list:
    """Minimal markdown → ReportLab flowables (headings, paragraphs, tables as mono)."""
    flowables: list = []
    body_style = ParagraphStyle(
        "ContractBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
    )
    h1_style = ParagraphStyle(
        "ContractH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    h2_style = ParagraphStyle(
        "ContractH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        spaceBefore=10,
        spaceAfter=6,
    )

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            flowables.append(Spacer(1, 0.12 * inch))
            continue
        if line.startswith("---"):
            flowables.append(Spacer(1, 0.2 * inch))
            continue
        safe = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        if line.startswith("# "):
            flowables.append(Paragraph(safe[2:], h1_style))
        elif line.startswith("## "):
            flowables.append(Paragraph(safe[3:], h2_style))
        elif line.startswith("|"):
            mono = ParagraphStyle(
                "ContractTable",
                parent=body_style,
                fontName="Courier",
                fontSize=8,
            )
            flowables.append(Paragraph(safe, mono))
        else:
            flowables.append(Paragraph(safe, body_style))
    return flowables


def render_markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    """Compile markdown contract body into a locked PDF binary."""
    if not markdown_text.strip():
        raise ValueError("Cannot render empty contract body to PDF")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="Promesa de Venta",
        author="All Blue Legal Engine",
    )
    styles = getSampleStyleSheet()
    story = _markdown_to_flowables(markdown_text, styles)
    try:
        doc.build(story)
    except Exception as exc:
        logger.exception("PDF build failed")
        raise ValueError("PDF compilation failed") from exc
    return buffer.getvalue()


def write_secure_pdf(transaction_id: str, markdown_text: str) -> tuple[Path, str]:
    """
    Render PDF to ``storage/secure_pdfs/`` and return ``(path, sha256_hex)``.
    """
    SECURE_PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf_bytes = render_markdown_to_pdf_bytes(markdown_text)
    document_hash = sha256_bytes(pdf_bytes)
    file_name = f"{transaction_id}_{document_hash[:12]}.pdf"
    pdf_path = SECURE_PDF_DIR / file_name
    try:
        pdf_path.write_bytes(pdf_bytes)
    except OSError as exc:
        logger.exception("Failed to write secure PDF: %s", pdf_path)
        raise ValueError("Secure PDF write failed") from exc
    logger.info(
        "Secure PDF written transaction_id=%s path=%s hash=%s",
        transaction_id,
        pdf_path.name,
        document_hash[:12],
    )
    return pdf_path, document_hash