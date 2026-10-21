"""Port for JWT token operations; implemented by the JWT adapter."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m01_access.domain.entities import (
    RoleCode,
    SessionKind,
    TokenPayload,
)


class TokenProvider(Protocol):
    """JWT creation and verification contract."""

    def create_access_token(
        self,
        *,
        user_id: UUID | None,
        session_id: UUID,
        roles: frozenset[RoleCode],
        kind: SessionKind,
    ) -> str:
        """Return a short-lived signed access token."""
        ...

    def create_refresh_token(self, *, session_id: UUID) -> str:
        """Return a longer-lived signed refresh token."""
        ...

    def decode_access_token(self, token: str) -> TokenPayload:
        """Decode and validate an access token; raise on failure."""
        ...

    def decode_refresh_token(self, token: str) -> UUID:
        """Return the *session_id* from a valid refresh token; raise on failure."""
        ...

    def hash_token(self, token: str) -> str:
        """Return a one-way hash of *token* for storage comparison."""
        ...
