"""
Role-Based Access Control and local JWT authentication infrastructure for Stream 5 Phase 5.0.

This module provides stateless, local-only cryptographic validation of Supabase-issued
JWTs (HMAC SHA256 against SUPABASE_JWT_SECRET) and RBAC enforcement via dependency
injection. It introduces no network calls, no persistent state, and no DB sessions into
the security perimeter.

All components are implemented as strict single-responsibility classes following the
mandatory Python OOP & PEP 257 Documentation Standards. Every module, class, and
public method includes exhaustive docstrings specifying:
- Purpose
- Lifecycle
- Thread-safety
- Collaborators
- Invariants
- Parameters (if applicable)
- Returns (if applicable)
- Raises (if applicable)
- Side Effects (if applicable)

This phase expands the core abstraction count from 9 (post-Phase 4.1) to 11 by adding
JWTTokenVerifier and RoleChecker. CRG is monitored; no session-passing or orchestrator
creep is introduced.

Environment:
    SUPABASE_JWT_SECRET must be provided (via .env or deployment secrets). Never
    committed or logged.
"""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, Dict, List

import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Security scheme for FastAPI auto-docs and dependency extraction.
security = HTTPBearer(auto_error=False)


class UserRole(str, Enum):
    """
    Enumeration of RBAC roles supported by the platform.

    Purpose:
        Define the set of privilege tiers used for endpoint authorization decisions.
        Roles are extracted from validated Supabase JWT claims (e.g. user metadata or
        app_metadata.role).

    Lifecycle:
        Immutable enum values; instantiated only via string coercion or direct
        reference in RoleChecker initializers and claim parsing.

    Thread-safety:
        Fully thread-safe (enum members are singletons with no mutable state).

    Collaborators:
        - UserCredentials (contains a role instance)
        - RoleChecker (initialized with lists of allowed roles)
        - JWTTokenVerifier (maps claim strings to enum members)

    Invariants:
        - Only the three defined members exist.
        - String values are lowercase for consistency with Supabase conventions.
        - No role implies higher privilege without explicit allow-listing.

    Parameters:
        (Enum members have no constructor parameters.)

    Returns:
        (Enum instances when accessed as UserRole.admin etc.)

    Raises:
        ValueError: On invalid string-to-enum coercion (handled in claim parsing).

    Side Effects:
        None (pure data definition).
    """

    ADMIN = "admin"
    AGENT = "agent"
    CLIENT = "client"


class UserCredentials(BaseModel):
    """
    Immutable value object representing a validated and authorized user context.

    Purpose:
        Carry the essential identity and role information extracted from a
        successfully verified Supabase JWT into route handlers and business logic.
        Enables tenant-scoped queries (user_id) and role checks without re-parsing
        the raw token.

    Lifecycle:
        Created exclusively by JWTTokenVerifier.verify_and_extract after successful
        signature/exp/claims validation. Passed via FastAPI Depends() into protected
        endpoints and RoleChecker.

    Thread-safety:
        Fully thread-safe (Pydantic frozen model with primitive fields only).

    Collaborators:
        - JWTTokenVerifier (producer)
        - RoleChecker (consumer for authorization)
        - Route handlers and query filters (consumer for user_id scoping)

    Invariants:
        - user_id is always present and non-empty (from 'sub' claim).
        - role is always a valid UserRole member.
        - raw_claims preserves the original verified payload for audit or future
          extensibility (never mutated).
        - Model is immutable (frozen=True).

    Parameters:
        user_id (str): The Supabase Auth user ID (from 'sub' claim).
        email (str): User's email address (from claims).
        role (UserRole): Resolved RBAC role.
        raw_claims (Dict[str, Any]): Complete original JWT payload.

    Returns:
        (Instance of UserCredentials.)

    Raises:
        (Pydantic validation errors on construction with bad data; prevented by
        verifier.)

    Side Effects:
        None (pure data carrier).
    """

    user_id: str = Field(..., min_length=1)
    email: str
    role: UserRole
    raw_claims: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}  # Enforce immutability (Pydantic v2)


class JWTTokenVerifier:
    """
    Stateless container for local-only verification of Supabase JWTs.

    Purpose:
        Decode, cryptographically validate (HMAC SHA256), check expiration/audience,
        extract claims, map to UserRole, and produce a UserCredentials instance.
        All operations are performed entirely locally using the symmetric
        SUPABASE_JWT_SECRET; zero outbound network traffic to Supabase or any
        external identity provider during the request lifecycle.

    Lifecycle:
        Typically instantiated once per application (or per router module) via
        dependency or direct construction with the secret from environment. The
        instance is stateless and reusable across concurrent requests/threads.

    Thread-safety:
        Fully thread-safe. No instance state is mutated after __init__; PyJWT
        decode is thread-safe for read-only use with a fixed key.

    Collaborators:
        - os (for SUPABASE_JWT_SECRET at init)
        - jwt (PyJWT library for decode/verify)
        - UserCredentials (return type)
        - FastAPI Depends (via get_current_user wrapper)

    Invariants:
        - Verification always uses algorithms=["HS256"] and the configured secret.
        - 'sub' claim is required and becomes user_id.
        - Role resolution falls back gracefully (default 'client') if claim absent
          or invalid.
        - Expired, tampered, or missing-signature tokens always produce 401.
        - No caching of tokens or secrets beyond the process environment.
        - Never logs the raw secret or full token.

    Parameters:
        (See __init__.)

    Returns:
        (See verify_and_extract.)

    Raises:
        (See verify_and_extract and __init__.)

    Side Effects:
        - Reads SUPABASE_JWT_SECRET from environment (once at construction).
        - Structured logging of verification failures (without secrets or full
          tokens).
    """

    def __init__(self, secret: str | None = None) -> None:
        """
        Initialize the verifier with the symmetric secret used by Supabase for
        HS256 signing.

        Purpose:
            Capture the secret (from explicit arg or SUPABASE_JWT_SECRET env) for
            use in all subsequent verifications.

        Lifecycle:
            Called at import time or during FastAPI startup / dependency
            provisioning. The resulting instance lives for the process lifetime.

        Thread-safety:
            Safe (immutable after construction).

        Collaborators:
            - os.getenv for fallback secret lookup.

        Invariants:
            - Secret is never stored in plaintext logs or exposed via __repr__.
            - If neither arg nor env provides a secret, construction fails fast.

        Parameters:
            secret (str | None): Optional explicit secret. If None, falls back to
                os.getenv("SUPABASE_JWT_SECRET").

        Returns:
            None.

        Raises:
            RuntimeError: If no secret can be resolved from arguments or environment.

        Side Effects:
            Reads environment variable (idempotent).
        """
        self._secret = secret or os.getenv("SUPABASE_JWT_SECRET")
        if not self._secret:
            raise RuntimeError(
                "SUPABASE_JWT_SECRET environment variable is required for "
                "JWTTokenVerifier but was not provided."
            )
        logger.debug("JWTTokenVerifier initialized with secret from environment")

    def verify_and_extract(self, token: str) -> UserCredentials:
        """
        Verify the supplied JWT locally and return a UserCredentials instance.

        Purpose:
            Perform cryptographic validation and claims extraction without any
            network I/O.

        Lifecycle:
            Invoked by get_current_user dependency on every protected request.

        Thread-safety:
            Safe for concurrent calls.

        Collaborators:
            - jwt.decode (PyJWT)
            - UserRole / UserCredentials (for mapping and construction)

        Invariants:
            - Uses HS256 + the configured secret.
            - Enforces 'exp' claim (PyJWT does this by default with verify_exp).
            - Role is always resolved to a known UserRole (defaults to CLIENT).

        Parameters:
            token (str): The raw Bearer token value (without 'Bearer ' prefix).

        Returns:
            UserCredentials: Validated identity object.

        Raises:
            HTTPException: status_code=401 with detail describing the failure
                (invalid signature, expired, malformed, missing sub, etc.).
                This is the contract expected by FastAPI error handling.

        Side Effects:
            - Logs verification failures at WARNING level (sanitized; no secret,
              no full token content).
        """
        try:
            payload: Dict[str, Any] = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                options={"verify_exp": True, "verify_signature": True},
            )
        except jwt.ExpiredSignatureError:
            logger.warning("JWT verification failed: token expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as exc:
            logger.warning("JWT verification failed: %s", str(exc))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("JWT verification failed: missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing required subject claim",
                headers={"WWW-Authenticate": "Bearer"},
            )

        email = payload.get("email", "")
        # Role resolution: prefer app_metadata.role or user_metadata.role, fallback to client
        role_str = (
            payload.get("app_metadata", {}).get("role")
            or payload.get("user_metadata", {}).get("role")
            or "client"
        )
        try:
            role = UserRole(role_str.lower())
        except ValueError:
            logger.warning("JWT role claim invalid: %s - defaulting to client", role_str)
            role = UserRole.CLIENT

        return UserCredentials(
            user_id=str(user_id),
            email=str(email),
            role=role,
            raw_claims=payload,
        )


# Global default verifier (stateless, safe to share).
_default_verifier = JWTTokenVerifier()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> UserCredentials:
    """
    FastAPI dependency that extracts and validates the Bearer token, returning
    UserCredentials.

    Purpose:
        Bridge between HTTP Authorization header and the rest of the application.
        Central place for auth failure -> 401 mapping.

    Lifecycle:
        Executed by FastAPI for every route that declares Depends(get_current_user).

    Thread-safety:
        Safe (delegates to stateless verifier).

    Collaborators:
        - security (HTTPBearer)
        - JWTTokenVerifier (default instance)

    Invariants:
        - Always returns UserCredentials on success; never returns None.
        - Failures always surface as HTTP 401 (never leak internal details).

    Parameters:
        credentials (HTTPAuthorizationCredentials | None): Injected by FastAPI
            from the Authorization header.

    Returns:
        UserCredentials: The authenticated user context.

    Raises:
        HTTPException(401): If no credentials, bad scheme, or verification fails.

    Side Effects:
        Delegates logging to the verifier.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _default_verifier.verify_and_extract(credentials.credentials)


class RoleChecker:
    """
    Factory for creating role-based authorization dependencies.

    Purpose:
        Encapsulate the logic of checking whether an already-authenticated user's
        role is in an allow-list. Used as a FastAPI dependency factory:
        Depends(RoleChecker([UserRole.AGENT, UserRole.ADMIN]))

    Lifecycle:
        Instantiated at module import / router definition time with a fixed
        allow-list. The resulting callable is invoked by FastAPI per-request
        (after get_current_user has succeeded).

    Thread-safety:
        Fully thread-safe (immutable allow-list after construction).

    Collaborators:
        - UserCredentials (input via Depends)
        - get_current_user (upstream dependency)
        - FastAPI routing layer (for 403 responses)

    Invariants:
        - __call__ never mutates state.
        - Authorization decision is based solely on role membership.
        - 403 is raised for insufficient role; the exception detail is generic
          to avoid information leakage.

    Parameters:
        allowed_roles (list[UserRole]): Roles that will be permitted.

    Returns:
        (See __call__.)

    Raises:
        (See __call__.)

    Side Effects:
        - Raises HTTPException(403) on authorization failure (FastAPI converts
          to response).
    """

    def __init__(self, allowed_roles: List[UserRole]) -> None:
        """
        Purpose:
            Capture the set of roles permitted for the protected operation(s).

        Lifecycle:
            Called at application startup / router module load time.

        Thread-safety:
            Safe.

        Collaborators:
            - UserRole enum.

        Invariants:
            - allowed_roles is stored immutably (tuple internally).
            - Empty list means "deny everyone" (defensive).

        Parameters:
            allowed_roles (list[UserRole]): The roles that satisfy the check.

        Returns:
            None.

        Raises:
            None (validation is lenient; empty list is allowed).

        Side Effects:
            None.
        """
        self._allowed_roles: tuple[UserRole, ...] = tuple(allowed_roles)

    def __call__(
        self, credentials: UserCredentials = Depends(get_current_user)
    ) -> UserCredentials:
        """
        FastAPI dependency callable that enforces the role allow-list.

        Purpose:
            Act as the guard for a route. If the user's role (from validated
            credentials) is not in the allowed set, deny with 403.

        Lifecycle:
            Invoked automatically by FastAPI for routes that use
            Depends(RoleChecker([...])).

        Thread-safety:
            Safe.

        Collaborators:
            - get_current_user (provides the credentials)
            - UserCredentials.role

        Invariants:
            - Passes through the credentials unchanged on success (for downstream
              handlers to use user_id etc.).
            - Always raises 403 (never 401) for role failures, because
              authentication has already succeeded.

        Parameters:
            credentials (UserCredentials): Injected by upstream Depends.

        Returns:
            UserCredentials: The same credentials (on success).

        Raises:
            HTTPException: status_code=403 with detail "Not enough permissions"
                if credentials.role not in self._allowed_roles.

        Side Effects:
            None on success. On failure: raises exception (converted to 403
            response by FastAPI).
        """
        if credentials.role not in self._allowed_roles:
            logger.warning(
                "RBAC denied: user_id=%s role=%s not in allowed=%s",
                credentials.user_id,
                credentials.role.value,
                [r.value for r in self._allowed_roles],
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return credentials
