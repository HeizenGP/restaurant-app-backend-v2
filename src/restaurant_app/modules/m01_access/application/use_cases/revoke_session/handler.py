"""Revoke the authenticated USER or GUEST session."""

from collections.abc import Callable
from datetime import UTC, datetime

from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.domain.entities import Principal
from restaurant_app.modules.m01_access.domain.errors import SessionExpiredError


def _utc_now() -> datetime:
    return datetime.now(UTC)


class RevokeSession:
    """Invalidate the persisted session immediately."""

    def __init__(
        self,
        sessions: SessionRepository,
        *,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._sessions = sessions
        self._now = now

    async def __call__(self, principal: Principal) -> None:
        if not await self._sessions.revoke(principal.session_id, revoked_at=self._now()):
            raise SessionExpiredError
