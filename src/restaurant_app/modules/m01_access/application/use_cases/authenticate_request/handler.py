"""Resolve a bearer token against current session, user, and role state."""

from collections.abc import Callable
from datetime import UTC, datetime

from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.domain.entities import Principal, SessionKind
from restaurant_app.modules.m01_access.domain.errors import (
    InvalidTokenError,
    SessionExpiredError,
    UserInactiveError,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AuthenticateRequest:
    """Never authorize from JWT role claims alone; reload mutable state from PostgreSQL."""

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

    async def __call__(self, access_token: str) -> Principal:
        payload = self._tokens.decode_access_token(access_token)
        session = await self._sessions.find_by_id(payload.session_id)
        if session is None or not session.is_active_at(self._now()):
            raise SessionExpiredError
        if session.kind is not payload.kind or session.user_id != payload.user_id:
            raise InvalidTokenError

        if session.kind is SessionKind.GUEST:
            return Principal(
                user_id=None,
                session_id=session.id,
                roles=frozenset(),
                kind=SessionKind.GUEST,
            )

        if session.user_id is None:
            raise InvalidTokenError
        user = await self._users.find_by_id(session.user_id)
        if user is None:
            raise InvalidTokenError
        if not user.is_active:
            raise UserInactiveError
        return Principal(
            user_id=user.id,
            session_id=session.id,
            roles=user.roles,
            kind=SessionKind.USER,
        )
