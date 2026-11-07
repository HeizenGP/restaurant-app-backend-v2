"""Authenticate or register a customer from a verified Google ID token."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from restaurant_app.modules.m01_access.application.issue_session import issue_user_session
from restaurant_app.modules.m01_access.application.ports.external_identity import (
    GoogleIdentityVerifier,
)
from restaurant_app.modules.m01_access.application.ports.session_repository import SessionRepository
from restaurant_app.modules.m01_access.application.ports.token_provider import TokenProvider
from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.errors import (
    EmailAlreadyRegisteredError,
    ExternalAuthenticationError,
    UserInactiveError,
)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LoginWithGoogle:
    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        verifier: GoogleIdentityVerifier,
        tokens: TokenProvider,
        *,
        refresh_ttl: timedelta,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._verifier = verifier
        self._tokens = tokens
        self._refresh_ttl = refresh_ttl
        self._now = now

    async def __call__(self, id_token: str) -> AuthenticationResult:
        identity = await self._verifier.verify(id_token)
        user = await self._users.find_by_google_subject(identity.subject)
        if user is None:
            if await self._users.find_by_email_with_hash(identity.email) is not None:
                raise ExternalAuthenticationError(
                    "A KAIRO account already uses this email. Sign in with your password."
                )
            try:
                user = await self._users.create_from_google(
                    display_name=identity.display_name,
                    email=identity.email,
                    google_subject=identity.subject,
                    avatar_url=identity.avatar_url,
                )
            except EmailAlreadyRegisteredError as error:
                raise ExternalAuthenticationError(
                    "A KAIRO account already uses this email. Sign in with your password."
                ) from error
        if not user.is_active:
            raise UserInactiveError
        return await issue_user_session(
            user=user,
            sessions=self._sessions,
            tokens=self._tokens,
            refresh_ttl=self._refresh_ttl,
            now=self._now(),
        )
