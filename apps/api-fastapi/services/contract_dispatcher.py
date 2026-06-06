"""
DocuSign Contract Dispatcher for Stream 6 Phase 1.0.
"""

from __future__ import annotations

import logging
from docusign_esign import ApiClient, EnvelopesApi, EnvelopeDefinition

from config.docusign_settings import DocusignSettings, get_docusign_settings

logger = logging.getLogger(__name__)


class ContractDispatcher:
    """
    Stateless execution container responsible for transmitting an envelope
    definition to the DocuSign API service and capturing the transaction receipt.

    Purpose:
        Wrap outbound envelope dispatch calls with standard exception handling,
        submitting the mapped contract envelope definition under the account's
        credentials.

    Lifecycle:
        Stateless and request-scoped. Initialized with an authenticated ApiClient
        per request/generation cycle, executing one transaction before being discarded.

    Thread-safety:
        Fully thread-safe as it maintains no mutable instance-level state and
        performs thread-safe network requests.

    Collaborators:
        - ApiClient (authenticated client with authorization headers)
        - DocusignSettings (configuration provider)
        - EnvelopesApi (DocuSign SDK service proxy client)

    Invariants:
        - Relies on the integration account ID for the dispatch call.
        - Raises a RuntimeError if the API call returns a payload without an envelope ID.
    """

    def __init__(
        self, api_client: ApiClient, settings: DocusignSettings | None = None
    ) -> None:
        """
        Purpose:
            Initialize the dispatcher with the authorized ApiClient and settings.

        Lifecycle:
            Constructed in route dependencies after DocuSign M2M authorization succeeds.

        Thread-safety:
            Safe.

        Collaborators:
            - ApiClient
            - DocusignSettings

        Invariants:
            - If settings is not provided, defaults to get_docusign_settings().

        Parameters:
            api_client (ApiClient): Fully authorized DocuSign API Client.
            settings (DocusignSettings | None): Configuration properties.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            None.
        """
        self._api_client = api_client
        self.settings = settings or get_docusign_settings()

    def dispatch(self, envelope_definition: EnvelopeDefinition) -> str:
        """
        Purpose:
            Transmit the envelope definition to DocuSign and return the unique
            envelope ID.

        Lifecycle:
            Invoked during the contract generation endpoint flow.

        Thread-safety:
            Safe.

        Collaborators:
            - EnvelopesApi (SDK class performing the HTTP POST request)

        Invariants:
            - Uses settings.api_account_id to target the correct DocuSign account.

        Parameters:
            envelope_definition (EnvelopeDefinition): Mapped signers and document data.

        Returns:
            str: Unique envelope ID (GUID) returned by DocuSign.

        Raises:
            RuntimeError: If DocuSign API fails or returns empty envelope ID.

        Side Effects:
            - Performs a network request (HTTP POST) to the DocuSign API servers.
        """
        envelopes_api = EnvelopesApi(self._api_client)

        try:
            summary = envelopes_api.create_envelope(
                account_id=self.settings.api_account_id,
                envelope_definition=envelope_definition,
            )
            envelope_id = summary.envelope_id
            if not envelope_id:
                raise RuntimeError("DocuSign create_envelope returned no envelope_id")

            logger.info("DocuSign envelope dispatched envelope_id=%s", envelope_id)
            return envelope_id
        except Exception as exc:
            logger.exception("Failed to dispatch DocuSign envelope")
            raise RuntimeError(f"DocuSign dispatch failed: {exc}") from exc
        
