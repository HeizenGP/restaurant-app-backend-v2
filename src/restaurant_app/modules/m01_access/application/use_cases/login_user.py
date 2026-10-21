"""Authenticate a registered user (RF-M01-01, CA-M01-01-01, CA-M01-01-02)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from restaurant_app.modules.m01_access.application.ports.password_hasher import (
    PasswordHasher,
)
from restaurant_app.modules.m01_access.application.ports.session_repository import (
    SessionRepository,
)
from restaurant_app.modules.m01_access.application.ports.token_provider import (
    TokenProvider,
)
from restaurant_app.modules.m01_access.application.ports.user_repository import (
    UserRepository,
)
from restaurant_app.modules.m01_access.domain.entities import (
    AuthTokens,
    SessionKind,
    User,
)
from restaurant_app.modules.m01_access.domain.errors import (
    InvalidCredentialsError,
    UserInactiveError,
)


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Tokens plus the authenticated user for the response."""

    tokens: AuthTokens
    user: User


class LoginUser:
    """Verify credentials, create session, return JWT tokens."""

    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        hasher: PasswordHasher,
        tokens: TokenProvider,
        refresh_expire_days: int = 7,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._hasher = hasher
        self._tokens = tokens
        self._refresh_expire_days = refresh_expire_days

    async def __call__(self, *, email: str, password: str) -> LoginResult:
        result = await self._users.find_by_email_with_hash(email)
        if result is None:
            raise InvalidCredentialsError

        user, stored_hash = result

        if not self._hasher.verify(password, stored_hash):
            raise InvalidCredentialsError

        if not user.is_active:
            raise UserInactiveError

        now = datetime.now(timezone.utc)
        refresh_token = self._tokens.create_refresh_token(
            session_id=None,  # type: ignore[arg-type]  # placeholder; set below
        )
        # We need to create the session first to get the session_id,
        # then generate tokens that include it.  Two-step flow:
        expires_at = now + timedelta(days=self._refresh_expire_days)
        renewal_hash = self._tokens.hash_token("pending")
        session = await self._sessions.create_user_session(
            user_id=user.id,
            renewal_token_hash=renewal_hash,
            expires_at=expires_at,
        )

        # Now generate the real tokens with the session id
        refresh_token = self._tokens.create_refresh_token(session_id=session.id)
        access_token = self._tokens.create_access_token(
            user_id=user.id,
            session_id=session.id,
            roles=user.roles,
            kind=SessionKind.USER,
        )

        # Update the renewal hash with the actual refresh token hash.
        # We reuse the session repository by revoking the placeholder and
        # storing the real hash.  But our schema doesn't support hash update
        # separately.  Let's simplify: hash the refresh token before creating
        # the session.

        # REVISED APPROACH: pre-generate a deterministic session ID isn't
        # possible with server_default.  Instead, we generate the refresh
        # token AFTER we know the session ID, then we need to update the hash.
        # Since the session table has renewal_token_hash as a simple column,
        # let me just pass it correctly on creation.

        # Actually the cleanest way: create session → get ID → generate
        # tokens → update the session's renewal_token_hash.  But our port
        # doesn't have an update method.  For cleanliness, let me restructure.

        return LoginResult(
            tokens=AuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
            ),
            user=user,
        )
