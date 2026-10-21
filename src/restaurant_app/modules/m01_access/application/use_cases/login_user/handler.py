"""Authenticate a registered user (RF-M01-01)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from restaurant_app.modules.m01_access.application.ports.password_hasher import (
    PasswordHasher,
)
from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.entities import AuthTokens, SessionKind
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
        if not self._hasher.verify(password, stored_hash):
            raise InvalidCredentialsError
        if not user.is_active:
            raise UserInactiveError

        now = self._now()
        session_id = uuid4()
        refresh_token = self._tokens.create_refresh_token(session_id=session_id)
        await self._sessions.create_user_session(
            session_id=session_id,
            user_id=user.id,
            renewal_token_hash=self._tokens.hash_token(refresh_token),
            created_at=now,
            expires_at=now + self._refresh_ttl,
        )
        access_token = self._tokens.create_access_token(
            user_id=user.id,
            session_id=session_id,
            roles=user.roles,
            kind=SessionKind.USER,
        )
        return AuthenticationResult(
            tokens=AuthTokens(access_token=access_token, refresh_token=refresh_token),
            user=user,
        )
