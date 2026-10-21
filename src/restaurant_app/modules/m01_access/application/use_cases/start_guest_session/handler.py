"""Create a limited guest session (RF-M01-02)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.entities import (
    AuthTokens,
    RoleCode,
    SessionKind,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class StartGuestSession:
    """Issue only a short-lived access token; Guest is not a seventh role."""

    def __init__(
        self,
        sessions: SessionRepository,
        tokens: TokenProvider,
        *,
        session_ttl: timedelta,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._sessions = sessions
        self._tokens = tokens
        self._session_ttl = session_ttl
        self._now = now

    async def __call__(self) -> AuthenticationResult:
        now = self._now()
        session_id = uuid4()
        await self._sessions.create_guest_session(
            session_id=session_id,
            created_at=now,
            expires_at=now + self._session_ttl,
        )
        access_token = self._tokens.create_access_token(
            user_id=None,
            session_id=session_id,
            roles=frozenset[RoleCode](),
            kind=SessionKind.GUEST,
        )
        return AuthenticationResult(
            tokens=AuthTokens(access_token=access_token, refresh_token=None),
            user=None,
        )
