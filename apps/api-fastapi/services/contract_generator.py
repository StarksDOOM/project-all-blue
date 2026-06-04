"""
Phase 4 — isolated legal document interpolation engine.

Pulls markdown templates and merges ``PropertyListing`` + ``TransactionSession`` fields.
Uses explicit ``str.format_map`` with a safe dict (no Jinja2 dependency) so missing
keys surface as ``[MISSING:field]`` instead of raising during compilation.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from models import PropertyListing, TransactionSession

logger = logging.getLogger(__name__)


class _SafeFormatDict(dict[str, str]):
    """Return placeholder for unknown template keys instead of raising KeyError."""

    def __missing__(self, key: str) -> str:
        logger.warning("Contract template missing interpolation key: %s", key)
        return f"[MISSING:{key}]"


PROMESA_DE_VENTA_TEMPLATE = """# PROMESA DE VENTA DE INMUEBLE

**República Dominicana**  
**Fecha de ejecución:** {execution_date}  
**Referencia de transacción:** {transaction_id}  
**Código de inmueble:** {remote_id}

---

## I. PARTES CONTRATANTES

**PROMITENTE VENDEDOR(A):**  
Nombre: **{seller_name}**  
Documento de identidad / RNC: **{seller_id_doc}**

**PROMITENTE COMPRADOR(A):**  
Nombre: **{buyer_name}**  
Documento de identidad / RNC: **{buyer_id_doc}**

---

## II. OBJETO DEL CONTRATO

| Campo | Detalle |
| :--- | :--- |
| **Descripción** | {property_title} |
| **Ubicación** | {property_sector}, {property_province} |
| **Área construida** | {square_meters} m² |
| **Área de terreno** | {sqm_land} m² |
| **Habitaciones** | {bedrooms} |
| **Baños** | {bathrooms} |
| **Precio de listado (portal)** | {list_price_display} |
| **Precio pactado (transacción)** | {agreed_price_display} |

El inmueble se transmitirá libre de gravámenes no declarados, salvo pacto escrito en contrario.

---

## III. PRECIO Y PAGOS

1. **Precio total acordado:** {agreed_price_display} ({currency}).
2. Las partes reconocen el precio de referencia del listado: {list_price_display}.
3. El saldo se pagará al otorgamiento de la escritura definitiva ante Notario Público.

---

## IV. LEY APLICABLE

Este instrumento se regirá por las leyes de la **República Dominicana**. Estado del documento: **{transaction_status}**.

---

## V. FIRMAS (Pendientes de formalización notarial)

| Vendedor(a) | Comprador(a) |
| :--- | :--- |
| {seller_name} | {buyer_name} |
| {seller_id_doc} | {buyer_id_doc} |

---
*Borrador generado por All Blue Legal Assembly Engine — requiere revisión de abogado licenciado.*
"""


SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _format_money(amount: float, currency: str) -> str:
    iso = (currency or "USD").upper()
    if iso == "DOP":
        return f"RD${amount:,.2f}"
    return f"US${amount:,.2f}"


def _execution_date_label() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.day} de {SPANISH_MONTHS[now.month - 1]} de {now.year}"


def build_contract_context(
    property_listing: PropertyListing,
    transaction: TransactionSession,
) -> dict[str, str]:
    """Merge property DB fields and transaction parameters for template substitution."""
    list_amount = property_listing.list_price or property_listing.price_usd
    currency = (transaction.currency or property_listing.listing_currency or "USD").upper()
    sqm_land = property_listing.sqm_land or 0.0

    return {
        "transaction_id": transaction.id,
        "transaction_status": transaction.status.value,
        "execution_date": _execution_date_label(),
        "remote_id": property_listing.remote_id,
        "property_title": property_listing.title,
        "property_sector": property_listing.sector,
        "property_province": property_listing.province,
        "square_meters": f"{property_listing.square_meters:,.2f}",
        "sqm_land": f"{sqm_land:,.2f}" if sqm_land > 0 else "N/D",
        "bedrooms": str(property_listing.bedrooms),
        "bathrooms": str(
            property_listing.bathrooms
            if property_listing.bathrooms % 1
            else int(property_listing.bathrooms)
        ),
        "list_price_display": _format_money(float(list_amount), currency),
        "agreed_price_display": _format_money(float(transaction.agreed_price), currency),
        "agreed_price": f"{transaction.agreed_price:.2f}",
        "currency": currency,
        "buyer_name": transaction.buyer_name,
        "buyer_id_doc": transaction.buyer_id_doc,
        "seller_name": transaction.seller_name,
        "seller_id_doc": transaction.seller_id_doc,
    }


def compile_promesa_de_venta(
    property_listing: PropertyListing,
    transaction: TransactionSession,
) -> str:
    """
    Compile Promesa de Venta markdown from property + transaction session.

    Raises:
        ValueError: When required party fields are empty after strip.
    """
    for label, value in (
        ("buyer_name", transaction.buyer_name),
        ("buyer_id_doc", transaction.buyer_id_doc),
        ("seller_name", transaction.seller_name),
        ("seller_id_doc", transaction.seller_id_doc),
    ):
        if not str(value or "").strip():
            raise ValueError(f"Missing required transaction field: {label}")

    context = build_contract_context(property_listing, transaction)
    safe_context = _SafeFormatDict(context)
    try:
        document = PROMESA_DE_VENTA_TEMPLATE.format_map(safe_context)
    except Exception as exc:
        logger.exception("Contract template interpolation failed: %s", exc)
        raise ValueError("Contract template compilation failed") from exc

    if "[MISSING:" in document:
        logger.warning(
            "Contract compiled with missing keys for transaction_id=%s",
            transaction.id,
        )
    return document


def infer_business_type(property_listing: PropertyListing) -> str:
    """Detect venta vs alquiler from enriched description metadata."""
    raw = (property_listing.raw_description or "").lower()
    title = (property_listing.title or "").lower()
    if "business_type=alquiler" in raw or "alquiler" in title:
        return "alquiler"
    return "venta"