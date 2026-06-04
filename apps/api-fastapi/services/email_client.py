"""
Email client abstractions and Resend provider for Stream 5 Phase 4.1.

This module provides a structural Protocol for email delivery and a concrete
production implementation using the Resend API via httpx. It replaces the
Phase 4.0 stub while preserving backward compatibility through dependency
injection.

Strict adherence to:
- Python OOP: Protocol for abstraction, concrete implementation classes.
- Absolute type safety.
- PEP 257: Every module, class, and method has comprehensive docstrings
  explicitly covering Purpose, Lifecycle, Thread-safety, Collaborators,
  Invariants, Parameters, Returns, Raises, and Side Effects.

No external network calls are made at import time. All I/O is encapsulated.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

import httpx


logger = logging.getLogger(__name__)


@runtime_checkable
class EmailClient(Protocol):
    """
    Structural Protocol defining the contract for any email delivery provider.

    Purpose:
        Decouple NotificationDispatcher from specific email gateways (Resend,
        SES, SendGrid, or stubs). Allows swapping implementations via DI
        without changing dispatcher logic.

    Lifecycle:
        - Providers are typically instantiated once (e.g. at app startup or
          per dispatcher instance) and reused.
        - For stateful clients (like httpx), use context managers internally
          for each send operation to ensure proper cleanup.

    Thread-safety:
        Implementations must be thread-safe for concurrent use from
        BackgroundTasks or multiple workers. httpx.Client is thread-safe
        when used with context managers per request; avoid sharing single
        client instances across threads without locks if stateful.

    Collaborators:
        - NotificationDispatcher (primary consumer via DI).
        - External email gateways (Resend HTTP API for production impl).
        - Configuration (os.environ for API keys).

    Invariants:
        - send_email must return bool: True on successful acceptance by gateway
          (typically 2xx), False on transient/permanent failure.
        - Must not raise for expected gateway errors; log and return False.
        - API keys and secrets never logged or exposed in errors.

    Parameters:
        (Defined per method)

    Returns:
        (Defined per method)

    Raises:
        (Defined per method; implementations should minimize uncaught raises)

    Side Effects:
        - Network I/O to email provider.
        - Logging at INFO/ERROR level for audit and debugging.
        - No direct DB mutations (delegated to caller/dispatcher).
    """

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """
        Send a transactional HTML email.

        Purpose:
            Deliver the rendered notification payload to the recipient via
            the chosen gateway.

        Lifecycle:
            Called from background task context after successful match
            persistence.

        Thread-safety:
            Must be safe for concurrent calls; use per-call clients or
            thread-local state where necessary.

        Collaborators:
            - httpx (in Resend impl) for HTTP transport.
            - os.environ for RESEND_API_KEY (in Resend impl).

        Invariants:
            - Returns True only if gateway accepted the message (2xx response).
            - On any failure (network, timeout, 4xx/5xx), log details and
              return False without crashing the caller.

        Parameters:
            to (str): Recipient email address.
            subject (str): Email subject line.
            html_body (str): Fully rendered HTML content (from NotificationCompiler).

        Returns:
            bool: True if delivery was accepted by the gateway, False otherwise.

        Raises:
            None: All errors are caught internally, logged, and result in
            False return. This prevents background task crashes from
            affecting match state updates.

        Side Effects:
            - Outbound HTTPS request to email provider API.
            - Structured logging of success/failure (no PII in sensitive fields).
            - Potential rate-limit backoff handling in future impls.
        """
        ...  # Protocol definition only


class StubEmailProvider:
    """
    No-op implementation of EmailClient for testing and development.

    Purpose:
        Provides a safe default that always "succeeds" without external
        dependencies. Used in Phase 4.0 and as fallback in 4.1 DI.

    Lifecycle:
        Stateless; can be instantiated freely or as singleton.

    Thread-safety:
        Fully thread-safe (no mutable state).

    Collaborators:
        - None (pure stub).

    Invariants:
        - Always returns True.
        - Never performs I/O.

    Parameters:
        (None for __init__)

    Returns:
        (See send_email)

    Raises:
        (None)

    Side Effects:
        - Logs at DEBUG level for traceability (no PII).
    """

    def __init__(self) -> None:
        """Initialize the stub provider (no configuration required)."""
        pass

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """
        Simulate successful email delivery.

        Purpose:
            Allow dispatcher and tests to exercise success paths without
            real email infrastructure.

        Lifecycle:
            Invoked from background task or test code.

        Thread-safety:
            Safe (no state).

        Collaborators:
            - logging module.

        Invariants:
            - Ignores all inputs after logging.
            - Always succeeds.

        Parameters:
            to (str): Recipient (logged at debug only).
            subject (str): Subject (logged at debug only).
            html_body (str): Body (length only logged to avoid large output).

        Returns:
            bool: Always True.

        Raises:
            None.

        Side Effects:
            - Debug log entry with recipient and subject (safe for tests).
        """
        logger.debug(
            "StubEmailProvider: simulated send to=%s subject=%s body_len=%d",
            to,
            subject,
            len(html_body) if html_body else 0,
        )
        return True


class ResendEmailProvider:
    """
    Production implementation of EmailClient using Resend's HTTP API via httpx.

    Purpose:
        Replace the stub with a real transactional email gateway for Phase 4.1.
        Handles API key from environment, constructs proper requests, and
        provides robust error handling for network and gateway issues.

    Lifecycle:
        - Instantiate with no args (reads RESEND_API_KEY from env at send time
          or init for early validation).
        - Use inside async context or per-send client creation for safety.
        - Designed for short-lived use in background tasks.

    Thread-safety:
        Each send_email creates its own httpx.Client inside a context manager,
        making the class safe for concurrent use from multiple BackgroundTasks
        or threads. No shared mutable client state.

    Collaborators:
        - httpx.Client (for HTTP with timeout and context management).
        - os.environ (for RESEND_API_KEY).
        - logging (for error details on non-2xx responses).

    Invariants:
        - RESEND_API_KEY must be present in environment at send time (validated).
        - All HTTP calls use explicit 10.0s timeout.
        - Non-2xx responses are logged with status and body snippet, then
          treated as failure (return False).
        - No secrets (API key) are ever logged.

    Parameters:
        (See __init__ and send_email)

    Returns:
        (See send_email)

    Raises:
        None from send_email (all transport/gateway errors are caught, logged,
        and result in False). RuntimeError possible only on missing config
        during explicit validation.

    Side Effects:
        - Outbound HTTPS POST to https://api.resend.com/emails .
        - Structured ERROR logging on failures (includes status code, no key).
        - Resource cleanup via httpx context manager.
    """

    RESEND_API_URL = "https://api.resend.com/emails"
    DEFAULT_TIMEOUT = 10.0

    def __init__(self) -> None:
        """
        Initialize Resend provider.

        Purpose:
            Prepare for sends; API key is resolved lazily from environment
            to support test injection if needed.

        Lifecycle:
            Created via DI in NotificationDispatcher or directly for tests.

        Thread-safety:
            Safe (immutable after init).

        Collaborators:
            - os (for getenv).

        Invariants:
            - Does not validate key at init time (allows lazy failure and
              easier testing).

        Parameters:
            None.

        Returns:
            None.

        Raises:
            None.

        Side Effects:
            None (pure initialization).
        """
        self._api_key: str | None = None

    def _get_api_key(self) -> str:
        """
        Resolve and cache the Resend API key from environment.

        Purpose:
            Centralize secret access with validation.

        Lifecycle:
            Called on first send.

        Thread-safety:
            Safe (write-once cache).

        Collaborators:
            - os.environ.

        Invariants:
            - Key is never logged.
            - Raises clear error if missing.

        Parameters:
            None.

        Returns:
            str: The API key.

        Raises:
            RuntimeError: If RESEND_API_KEY is not set in the environment.

        Side Effects:
            - Caches the key for subsequent calls in this instance.
        """
        if self._api_key is None:
            key = os.getenv("RESEND_API_KEY")
            if not key:
                raise RuntimeError(
                    "RESEND_API_KEY environment variable is required for "
                    "ResendEmailProvider but was not found."
                )
            self._api_key = key
        return self._api_key

    async def send_email(self, to: str, subject: str, html_body: str) -> bool:
        """
        Send email via Resend API.

        Purpose:
            Perform the actual delivery using Resend's transactional email
            service with production-grade resilience (timeouts, error logging).

        Lifecycle:
            Called from NotificationDispatcher's background task after
            successful HTML rendering.

        Thread-safety:
            Safe via per-call httpx.Client context manager.

        Collaborators:
            - httpx.Client (with timeout).
            - Resend API (external).

        Invariants:
            - Uses 10.0s total timeout for connect + read.
            - On any non-2xx response: log error details (status, body prefix),
              return False.
            - On network/timeout: log, return False.
            - Success only on 2xx.

        Parameters:
            to (str): Recipient address (passed through to Resend 'to' field).
            subject (str): Subject line.
            html_body (str): HTML content for the email body.

        Returns:
            bool: True if Resend accepted the email (2xx), False on any error.

        Raises:
            None (all exceptions during HTTP are caught and result in False).

        Side Effects:
            - One HTTPS POST request to Resend.
            - ERROR level logs on failure (contains status code and truncated
              response body; never includes API key).
            - Proper client cleanup via context manager.
        """
        api_key = self._get_api_key()

        payload = {
            "from": "alerts@allblue.example",  # TODO: make configurable
            "to": to,
            "subject": subject,
            "html": html_body,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Use context manager for each send to ensure isolation and cleanup.
            # Explicit timeout prevents hanging on slow gateways.
            async with httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    self.RESEND_API_URL, json=payload, headers=headers
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        "ResendEmailProvider: email accepted for to=%s subject=%s",
                        to,
                        subject,
                    )
                    return True
                else:
                    # Log non-2xx for diagnostics; truncate body to avoid log bloat.
                    body_preview = response.text[:200] if response.text else ""
                    logger.error(
                        "ResendEmailProvider: gateway rejection status=%s to=%s subject=%s body=%s",
                        response.status_code,
                        to,
                        subject,
                        body_preview,
                    )
                    return False

        except httpx.TimeoutException as exc:
            logger.error(
                "ResendEmailProvider: timeout after %ss for to=%s subject=%s: %s",
                self.DEFAULT_TIMEOUT,
                to,
                subject,
                exc,
            )
            return False
        except httpx.RequestError as exc:
            logger.error(
                "ResendEmailProvider: network error for to=%s subject=%s: %s",
                to,
                subject,
                exc,
            )
            return False
        except Exception as exc:
            # Catch-all for unexpected issues during send.
            logger.exception(
                "ResendEmailProvider: unexpected error sending to=%s subject=%s",
                to,
                subject,
            )
            return False
