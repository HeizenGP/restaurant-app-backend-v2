"""Port for auth-session persistence; implemented by outbound adapters."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m01_access.domain.entities import AuthSession


class SessionRepository(Protocol):
    """Contract consumed by M01 use cases."""

    async def create_user_session(
        self,
        *,
        user_id: UUID,
        renewal_token_hash: str,
        expires_at: datetime,
    ) -> AuthSession:
        """Persist a new USER session and return the domain entity."""
        ...

    async def create_guest_session(self, *, expires_at: datetime) -> AuthSession:
        """Persist a new GUEST session and return the domain entity."""
        ...

    async def find_by_id(self, session_id: UUID) -> AuthSession | None:
        """Return session regardless of active/revoked status, or *None*."""
        ...

    async def revoke(self, session_id: UUID) -> bool:
        """Revoke session. Return *True* if revoked, *False* if not found."""
        ...
