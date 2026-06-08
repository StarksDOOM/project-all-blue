"""
DocuSeal Contract Dispatcher.

Transmits template-based signature requests to the DocuSeal REST API.
"""

from __future__ import annotations

import logging
import httpx

from config.docuseal_settings import DocuSealSettings, get_docuseal_settings

logger = logging.getLogger(__name__)


class DocuSealDispatcher:
    """
    Stateless execution container responsible for transmitting signature requests to DocuSeal.

    Purpose:
        Perform template-based signature request creation using DocuSeal API submissions.
        Constructs the submitters payload and handles standard error responses.

    Lifecycle:
        Stateless and request-scoped. Instantiated on-demand during contract generation.

    Thread-safety:
        Fully thread-safe. Uses an isolated HTTPX client per call.

    Collaborators:
        - DocuSealSettings (configuration settings provider)
        - httpx.Client (HTTP client for API requests)

    Invariants:
        - Requires template ID and API key to be set in environment settings.
        - Robustly parses both single dictionary and array-based JSON responses.
    """

    def __init__(self, settings: DocuSealSettings | None = None) -> None:
        """
        Initialize the DocuSealDispatcher with settings.

        Parameters:
            settings (DocuSealSettings | None): Configuration properties. Defaults to global loader.
        """
        self.settings = settings or get_docuseal_settings()

    def dispatch(self, property_id: str, buyer_email: str, agent_email: str) -> str:
        """
        Transmit the signature request to the DocuSeal API and return the submission ID.

        Parameters:
            property_id (str): Unique identifier of the real estate listing.
            buyer_email (str): Target email for the Buyer role.
            agent_email (str): Target email for the Agent role.

        Returns:
            str: Unique submission ID returned by DocuSeal.

        Raises:
            RuntimeError: If configuration is invalid, request fails, or submission ID is missing.
        """
        settings = self.settings
        if not settings.is_enabled:
            raise RuntimeError("DocuSeal is not configured. Set DOCUSEAL_API_KEY and DOCUSEAL_TEMPLATE_ID.")

        url = f"{settings.base_url}/api/submissions"
        headers = {
            "X-Auth-Token": settings.api_key,
            "Content-Type": "application/json",
        }

        # Submitter roles in the template: "Buyer" and "Agent"
        payload = {
            "template_id": int(settings.template_id),
            "send_email": True,
            "submitters": [
                {
                    "role": "Buyer",
                    "email": buyer_email,
                    "name": "Cliente Comprador Demo",
                },
                {
                    "role": "Agent",
                    "email": agent_email,
                    "name": "Agente",
                },
            ],
            "metadata": {
                "external_id": property_id,
            },
        }

        logger.info(
            "Dispatching DocuSeal submission request: url=%s template_id=%s property_id=%s",
            url,
            settings.template_id,
            property_id,
        )

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                response_data = response.json()

                logger.info("DocuSeal submission response: %s", response_data)

                # Robustly handle both list of submitters/submissions or single dict
                if isinstance(response_data, list):
                    if not response_data:
                        raise RuntimeError("DocuSeal returned an empty list of submissions")
                    submission_id = response_data[0].get("id") or response_data[0].get("submission_id")
                elif isinstance(response_data, dict):
                    submission_id = response_data.get("id") or response_data.get("submission_id")
                else:
                    raise RuntimeError(f"Unexpected response type from DocuSeal: {type(response_data)}")

                if not submission_id:
                    raise RuntimeError(f"DocuSeal response missing submission ID: {response_data}")

                # Return submission ID as string
                return str(submission_id)

        except httpx.HTTPStatusError as exc:
            logger.error("DocuSeal API returned error status: %s body=%s", exc.response.status_code, exc.response.text)
            raise RuntimeError(f"DocuSeal API call failed: {exc.response.text}") from exc
        except Exception as exc:
            logger.exception("Unexpected error when calling DocuSeal API")
            raise RuntimeError(f"DocuSeal dispatch failed: {exc}") from exc
