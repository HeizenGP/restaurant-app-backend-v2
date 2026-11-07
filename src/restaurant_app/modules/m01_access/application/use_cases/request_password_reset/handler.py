"""Create and deliver a non-enumerating password recovery token."""

import hashlib
import secrets
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from restaurant_app.modules.m01_access.application.ports.password_reset import (
    PasswordResetMessenger,
    PasswordResetRepository,
)
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RequestPasswordReset:
    def __init__(
        self,
        users: UserRepository,
        resets: PasswordResetRepository,
        messenger: PasswordResetMessenger,
        *,
        token_ttl: timedelta,
        now: Callable[[], datetime] = _utc_now,
        token_factory: Callable[[], str] = lambda: secrets.token_urlsafe(32),
    ) -> None:
        self._users = users
        self._resets = resets
        self._messenger = messenger
        self._token_ttl = token_ttl
        self._now = now
        self._token_factory = token_factory

    async def __call__(self, email: str) -> None:
        token = self._token_factory()
        digest = hashlib.sha256(token.encode()).hexdigest()
        result = await self._users.find_by_email_with_hash(email.strip().casefold())
        if result is None:
            return
        user, _ = result
        if not user.is_active:
            return
        now = self._now()
        await self._resets.replace_active_token(
            user_id=user.id,
            token_hash=digest,
            created_at=now,
            expires_at=now + self._token_ttl,
        )
        await self._messenger.send_password_reset(
            email=user.email,
            display_name=user.display_name,
            token=token,
        )
