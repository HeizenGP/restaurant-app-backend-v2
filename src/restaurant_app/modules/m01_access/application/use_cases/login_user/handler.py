"""Authenticate a registered user (RF-M01-01)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from restaurant_app.modules.m01_access.application.issue_session import issue_user_session
from restaurant_app.modules.m01_access.application.ports.password_hasher import (
    PasswordHasher,
)
from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.errors import (
    InvalidCredentialsError,
    UserInactiveError,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LoginUser:
    """Verify credentials and persist the exact digest of the issued refresh token."""

    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        hasher: PasswordHasher,
        tokens: TokenProvider,
        *,
        refresh_ttl: timedelta,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._hasher = hasher
        self._tokens = tokens
        self._refresh_ttl = refresh_ttl
        self._now = now

    async def __call__(self, *, email: str, password: str) -> AuthenticationResult:
        result = await self._users.find_by_email_with_hash(email.strip().casefold())
        if result is None:
            self._hasher.verify_dummy(password)
            raise InvalidCredentialsError

        user, stored_hash = result
        if stored_hash is None:
            self._hasher.verify_dummy(password)
            raise InvalidCredentialsError
        if not self._hasher.verify(password, stored_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise UserInactiveError

        return await issue_user_session(
            user=user,
            sessions=self._sessions,
            tokens=self._tokens,
            refresh_ttl=self._refresh_ttl,
            now=self._now(),
        )
