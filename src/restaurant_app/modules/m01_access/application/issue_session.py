"""Shared session issuance for verified user identities."""

from datetime import datetime, timedelta
from uuid import uuid4

from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.entities import AuthTokens, SessionKind, User


async def issue_user_session(
    *,
    user: User,
    sessions: SessionRepository,
    tokens: TokenProvider,
    refresh_ttl: timedelta,
    now: datetime,
) -> AuthenticationResult:
    session_id = uuid4()
    refresh_token = tokens.create_refresh_token(session_id=session_id)
    await sessions.create_user_session(
        session_id=session_id,
        user_id=user.id,
        renewal_token_hash=tokens.hash_token(refresh_token),
        created_at=now,
        expires_at=now + refresh_ttl,
    )
    access_token = tokens.create_access_token(
        user_id=user.id,
        session_id=session_id,
        roles=user.roles,
        kind=SessionKind.USER,
    )
    return AuthenticationResult(
        tokens=AuthTokens(access_token=access_token, refresh_token=refresh_token),
        user=user,
    )
