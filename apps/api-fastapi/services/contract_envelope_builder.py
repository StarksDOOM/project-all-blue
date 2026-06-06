"""
DocuSign Contract Envelope Builder for Stream 6 Phase 1.0.
"""

from __future__ import annotations

import base64
import logging
from docusign_esign import (
    Document,
    EnvelopeDefinition,
    Recipients,
    Signer,
    SignHere,
    Tabs,
)

from models import PropertyListing
from services.auth import UserCredentials

logger = logging.getLogger(__name__)


class ContractEnvelopeBuilder:
    """
    Stateless builder that maps property listings and user credentials into a
    DocuSign EnvelopeDefinition.

    Purpose:
        Construct the schema-compliant DocuSign envelope payload for digital
        signature, embedding the property listing metadata (price, sector, title)
        and routing it to the authenticated agent and a mock buyer.

    Lifecycle:
        Stateless and request-scoped. Instantiated on-demand during contract
        generation requests to map models to API definitions.

    Thread-safety:
        Fully thread-safe as it holds no mutable state or database sessions.

    Collaborators:
        - PropertyListing (source model for contract variables)
        - UserCredentials (agent credentials for mapping the signer/sender)
        - docusign_esign (EnvelopeDefinition, Signer, Document schemas)

    Invariants:
        - Always returns a "sent" status envelope so it is dispatched immediately.
        - Uses auto-place anchor tagging (/sn1/ and /sn2/) in the generated HTML
          document to place signatures dynamically.
    """

    def build_envelope(
        self, listing: PropertyListing, credentials: UserCredentials
    ) -> EnvelopeDefinition:
        """
        Purpose:
            Assemble the complete DocuSign EnvelopeDefinition from listing metadata.

        Lifecycle:
            Invoked inside the contract generation route before calling the
            dispatcher.

        Thread-safety:
            Safe.

        Collaborators:
            - PropertyListing
            - UserCredentials

        Invariants:
            - Generates an HTML contract body dynamically using Listing variables.
            - Encodes the HTML body in base64.
            - Configures buyer and agent signers with appropriate routing order.

        Parameters:
            listing (PropertyListing): The active real estate listing being contracted.
            credentials (UserCredentials): Credentials of the authenticated agent generating the contract.

        Returns:
            EnvelopeDefinition: Complete envelope setup ready for dispatch.

        Raises:
            None.

        Side Effects:
            None (pure mapping logic).
        """
        # Build the dynamic HTML document body
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Acuerdo de Reserva de Propiedad</title>
<style>
    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333333; line-height: 1.6; padding: 30px; }}
    h1 {{ text-align: center; color: #1e3a8a; font-size: 24px; border-bottom: 2px solid #1e3a8a; padding-bottom: 10px; }}
    .meta-box {{ background-color: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 6px; padding: 15px; margin: 20px 0; }}
    .meta-title {{ font-weight: bold; margin-bottom: 5px; }}
    .section-title {{ font-size: 18px; color: #1e3a8a; margin-top: 30px; margin-bottom: 10px; font-weight: bold; }}
    .signatures {{ margin-top: 60px; }}
    .sig-table {{ width: 100%; border-collapse: collapse; }}
    .sig-table td {{ width: 50%; padding: 10px; vertical-align: top; }}
    .anchor-text {{ color: #ffffff; font-size: 8px; user-select: none; }}
</style>
</head>
<body>
    <h1>ACUERDO DE RESERVA DE PROPIEDAD</h1>
    <p>El presente documento constituye un acuerdo preliminar de reserva de bienes raíces, celebrado de conformidad con las leyes de la República Dominicana.</p>

    <div class="meta-box">
        <div class="meta-title">Detalles de la Propiedad Reservada:</div>
        <table>
            <tr><td><strong>Referencia:</strong></td><td>{listing.id}</td></tr>
            <tr><td><strong>Título:</strong></td><td>{listing.title}</td></tr>
            <tr><td><strong>Sector / Ubicación:</strong></td><td>{listing.sector}, {listing.province}</td></tr>
            <tr><td><strong>Precio acordado de venta:</strong></td><td>USD {listing.price_usd:,.2f}</td></tr>
        </table>
    </div>

    <div class="section-title">1. Objeto del Acuerdo</div>
    <p>El comprador manifiesta su interés en adquirir y el agente autorizado confirma la disponibilidad para la reserva de la propiedad descrita en este documento, bajo el precio acordado de venta.</p>

    <div class="section-title">2. Firmas y Consentimiento</div>
    <p>Al firmar este documento, las partes aceptan las condiciones básicas descritas anteriormente y se comprometen a proceder con la redacción del contrato definitivo de compraventa.</p>

    <div class="signatures">
        <table class="sig-table">
            <tr>
                <td>
                    <strong>Comprador (Cliente):</strong><br><br><br>
                    _________________________________<br>
                    Firma Comprador<br>
                    <span class="anchor-text">/sn1/</span>
                </td>
                <td>
                    <strong>Agente Inmobiliario:</strong><br>
                    Email: {credentials.email}<br><br>
                    _________________________________<br>
                    Firma Agente<br>
                    <span class="anchor-text">/sn2/</span>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""
        # Base64 encode the HTML contract
        b64_content = base64.b64encode(html_content.encode("utf-8")).decode("ascii")

        # Create DocuSign Document object
        document = Document(
            document_base64=b64_content,
            name="Acuerdo_de_Reserva.html",
            file_extension="html",
            document_id="1",
        )

        # Setup signature locations (AutoPlace anchors)
        sign_here_buyer = SignHere(
            anchor_string="/sn1/",
            anchor_units="pixels",
            anchor_y_offset="-15",
            anchor_x_offset="10",
        )
        sign_here_agent = SignHere(
            anchor_string="/sn2/",
            anchor_units="pixels",
            anchor_y_offset="-15",
            anchor_x_offset="10",
        )

        # Build Signer objects
        buyer_signer = Signer(
            email="cliente.comprador@example.com",
            name="Cliente Comprador Demo",
            recipient_id="1",
            routing_order="1",
            role_name="Buyer",
            tabs=Tabs(sign_here_tabs=[sign_here_buyer]),
        )
        agent_signer = Signer(
            email=credentials.email,
            name=f"Agente ({credentials.role.value})",
            recipient_id="2",
            routing_order="2",
            role_name="Agent",
            tabs=Tabs(sign_here_tabs=[sign_here_agent]),
        )

        # Compile envelope definition
        envelope_definition = EnvelopeDefinition(
            email_subject=f"Reserva de Propiedad - {listing.title}",
            documents=[document],
            recipients=Recipients(signers=[buyer_signer, agent_signer]),
            status="sent",
        )

        logger.info(
            "DocuSign envelope definition built successfully listing_id=%s agent=%s",
            listing.id,
            credentials.email,
        )
        return envelope_definition
