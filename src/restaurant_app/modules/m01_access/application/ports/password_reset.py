"""Ports used by the password recovery slices."""

from datetime import datetime
from typing import Protocol
from uuid import UUID


class PasswordResetRepository(Protocol):
    async def replace_active_token(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Invalidate older tokens and persist one new digest."""
        ...

    async def consume(self, *, token_hash: str, now: datetime) -> UUID | None:
        """Atomically consume a valid token and return its user id."""
        ...


class PasswordResetMessenger(Protocol):
    async def send_password_reset(self, *, email: str, display_name: str, token: str) -> None:
        """Deliver the opaque reset token through a side channel."""
        ...
