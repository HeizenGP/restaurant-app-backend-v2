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
        session_id: UUID,
        user_id: UUID,
        renewal_token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        """Persist a new USER session and return the domain entity."""
        ...

    async def create_guest_session(
        self,
        *,
        session_id: UUID,
        created_at: datetime,
        expires_at: datetime,
    ) -> AuthSession:
        """Persist a new GUEST session and return the domain entity."""
        ...

    async def find_by_id(self, session_id: UUID) -> AuthSession | None:
        """Return session regardless of active/revoked status, or *None*."""
        ...

    async def rotate_renewal_token(
        self,
        *,
        session_id: UUID,
        expected_hash: str,
        replacement_hash: str,
    ) -> bool:
        """Atomically replace a refresh digest once; reject concurrent replay."""
        ...

    async def revoke(self, session_id: UUID, *, revoked_at: datetime) -> bool:
        """Revoke session. Return *True* if revoked, *False* if not found."""
        ...

    async def revoke_all_for_user(self, user_id: UUID, *, revoked_at: datetime) -> int:
        """Revoke all active sessions after a credential reset."""
        ...
