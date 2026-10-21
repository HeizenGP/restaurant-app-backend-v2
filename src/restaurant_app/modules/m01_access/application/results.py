"""Framework-free result objects shared by M01 application handlers."""

from dataclasses import dataclass

from restaurant_app.modules.m01_access.domain.entities import AuthTokens, User


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Issued credentials and the optional registered-user identity."""

    tokens: AuthTokens
    user: User | None
