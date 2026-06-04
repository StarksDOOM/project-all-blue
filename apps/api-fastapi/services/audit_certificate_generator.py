"""
Phase 6 — one-page Certificado de Ejecución Digital (cryptographic receipt).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

AUDIT_RECEIPTS_DIR = (
    Path(__file__).resolve().parents[1] / "storage" / "secure_pdfs" / "audit_receipts"
)


@dataclass(frozen=True)
class AuditCertificateInput:
    transaction_id: str
    property_id: str
    property_title: str
    esign_envelope_id: str
    esign_status: str
    document_hash: str
    buyer: dict[str, str]
    seller: dict[str, str]
    executed_at: str


def _signer_table_rows(signer: dict[str, str]) -> list[list[str]]:
    return [
        ["Rol", signer.get("role", "—")],
        ["Nombre", signer.get("name", "—")],
        ["Correo", signer.get("email", "—")],
        ["Firmado", signer.get("signed_at", "—")],
    ]


def render_audit_certificate_pdf(data: AuditCertificateInput) -> bytes:
    """Build a single-page official execution summary PDF."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Certificado de Ejecución Digital",
        author="All Blue Audit Engine",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
    )
    label_style = ParagraphStyle(
        "CertLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e293b"),
    )
    body_style = ParagraphStyle(
        "CertBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#334155"),
    )

    story: list[Any] = [
        Paragraph("Certificado de Ejecución Digital", title_style),
        Spacer(1, 6),
        Paragraph(
            "Comprobante criptográfico de cierre — Promesa de Venta (República Dominicana)",
            subtitle_style,
        ),
        Spacer(1, 18),
        Paragraph("<b>Identificadores de transacción</b>", label_style),
        Spacer(1, 6),
        Paragraph(f"Transaction ID: {data.transaction_id}", body_style),
        Paragraph(f"Property ID: {data.property_id}", body_style),
        Paragraph(f"Inmueble: {data.property_title}", body_style),
        Spacer(1, 12),
        Paragraph("<b>DocuSign eSign</b>", label_style),
        Spacer(1, 6),
        Paragraph(f"esign_envelope_id: {data.esign_envelope_id}", body_style),
        Paragraph(f"esign_status: {data.esign_status}", body_style),
        Paragraph(f"Ejecutado: {data.executed_at}", body_style),
        Spacer(1, 12),
        Paragraph("<b>Integridad del contrato firmado (SHA-256)</b>", label_style),
        Spacer(1, 6),
        Paragraph(data.document_hash, body_style),
        Spacer(1, 16),
        Paragraph("<b>Partes — metadatos de firma</b>", label_style),
        Spacer(1, 10),
    ]

    buyer_table = Table(
        _signer_table_rows(data.buyer),
        colWidths=[1.1 * inch, 4.9 * inch],
        hAlign="LEFT",
    )
    buyer_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    seller_table = Table(
        _signer_table_rows(data.seller),
        colWidths=[1.1 * inch, 4.9 * inch],
        hAlign="LEFT",
    )
    seller_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    story.extend([buyer_table, Spacer(1, 10), seller_table])
    doc.build(story)
    return buffer.getvalue()


def write_audit_certificate(data: AuditCertificateInput) -> Path:
    """Persist certificate PDF under ``storage/secure_pdfs/audit_receipts/``."""
    AUDIT_RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_bytes = render_audit_certificate_pdf(data)
    path = AUDIT_RECEIPTS_DIR / f"{data.transaction_id}_certificate.pdf"
    path.write_bytes(pdf_bytes)
    logger.info("Audit certificate written transaction_id=%s path=%s", data.transaction_id, path.name)
    return path