"""Consume a recovery token and replace the local password."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from restaurant_app.modules.m01_access.application.ports.password_hasher import PasswordHasher
from restaurant_app.modules.m01_access.application.ports.password_reset import (
    PasswordResetRepository,
)
from restaurant_app.modules.m01_access.application.ports.session_repository import SessionRepository
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.domain.errors import InvalidPasswordResetTokenError


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ResetPassword:
    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        resets: PasswordResetRepository,
        hasher: PasswordHasher,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._resets = resets
        self._hasher = hasher
        self._now = now

    async def __call__(self, *, token: str, new_password: str) -> None:
        now = self._now()
        digest = hashlib.sha256(token.encode()).hexdigest()
        user_id = await self._resets.consume(token_hash=digest, now=now)
        if user_id is None:
            raise InvalidPasswordResetTokenError
        await self._users.update_password(user_id, password_hash=self._hasher.hash(new_password))
        await self._sessions.revoke_all_for_user(user_id, revoked_at=now)
