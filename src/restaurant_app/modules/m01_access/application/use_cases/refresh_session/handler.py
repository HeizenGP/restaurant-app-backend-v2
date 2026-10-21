"""Rotate a refresh token and issue access with current roles."""

from collections.abc import Callable
from datetime import UTC, datetime

from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.entities import AuthTokens, SessionKind
from restaurant_app.modules.m01_access.domain.errors import (
    InvalidTokenError,
    SessionExpiredError,
    UserInactiveError,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RefreshSession:
    """Use one-time refresh rotation so concurrent replay has a single winner."""

    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        tokens: TokenProvider,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._tokens = tokens
        self._now = now

    async def __call__(self, refresh_token: str) -> AuthenticationResult:
        session_id = self._tokens.decode_refresh_token(refresh_token)
        session = await self._sessions.find_by_id(session_id)
        if session is None or not session.is_active_at(self._now()):
            raise SessionExpiredError
        if (
            session.kind is not SessionKind.USER
            or session.user_id is None
            or session.renewal_token_hash is None
            or not self._tokens.token_matches_hash(refresh_token, session.renewal_token_hash)
        ):
            raise InvalidTokenError

        user = await self._users.find_by_id(session.user_id)
        if user is None:
            raise InvalidTokenError
        if not user.is_active:
            raise UserInactiveError

        replacement = self._tokens.create_refresh_token(session_id=session.id)
        rotated = await self._sessions.rotate_renewal_token(
            session_id=session.id,
            expected_hash=session.renewal_token_hash,
            replacement_hash=self._tokens.hash_token(replacement),
        )
        if not rotated:
            raise InvalidTokenError

        access_token = self._tokens.create_access_token(
            user_id=user.id,
            session_id=session.id,
            roles=user.roles,
            kind=SessionKind.USER,
        )
        return AuthenticationResult(
            tokens=AuthTokens(access_token=access_token, refresh_token=replacement),
            user=user,
        )
