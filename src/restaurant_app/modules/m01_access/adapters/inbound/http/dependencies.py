"""HTTP composition root for M01 authentication and authorization dependencies."""

from datetime import timedelta
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from restaurant_app.core.dependencies import AppSettings, DatabaseSession
from restaurant_app.modules.m01_access.adapters.outbound import (
    Argon2PasswordHasher,
    JwtTokenProvider,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from restaurant_app.modules.m01_access.application.use_cases.authenticate_request import (
    AuthenticateRequest,
)
from restaurant_app.modules.m01_access.application.use_cases.authorize_roles import AuthorizeRoles
from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode
from restaurant_app.modules.m01_access.domain.errors import InvalidTokenError

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


@lru_cache(maxsize=1)
def get_password_hasher() -> Argon2PasswordHasher:
    """Reuse the immutable Argon2 configuration."""

    return Argon2PasswordHasher()


def build_token_provider(settings: AppSettings) -> JwtTokenProvider:
    """Build a request-local adapter without exposing the signing secret."""

    return JwtTokenProvider(
        secret=settings.jwt_secret.get_secret_value(),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        access_ttl=timedelta(minutes=settings.jwt_access_ttl_minutes),
        refresh_ttl=timedelta(days=settings.jwt_refresh_ttl_days),
    )


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: DatabaseSession,
    settings: AppSettings,
) -> Principal:
    """Authenticate Bearer credentials against current persisted state."""

    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise InvalidTokenError
    return await AuthenticateRequest(
        SqlAlchemyUserRepository(session),
        SqlAlchemySessionRepository(session),
        build_token_provider(settings),
    )(credentials.credentials)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    """HTTP-level guard; the role-assignment handler repeats this check."""

    AuthorizeRoles(RoleCode.ADMIN)(principal)
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]
