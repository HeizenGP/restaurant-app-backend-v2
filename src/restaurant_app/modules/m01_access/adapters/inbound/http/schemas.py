"""Pydantic HTTP contracts for M01; domain and application stay framework-free."""

from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from restaurant_app.modules.m01_access.application.results import AuthenticationResult
from restaurant_app.modules.m01_access.domain.entities import RoleCode, SessionKind, User


class StrictRequest(BaseModel):
    """Reject unknown request fields and trim ordinary string inputs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RegisterRequest(StrictRequest):
    display_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        normalized = value.casefold()
        if normalized.count("@") != 1:
            raise ValueError("email must contain one '@'")
        local, domain = normalized.split("@", maxsplit=1)
        if not local or not domain or any(character.isspace() for character in normalized):
            raise ValueError("email is invalid")
        return normalized


class LoginRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class RefreshRequest(StrictRequest):
    refresh_token: SecretStr = Field(min_length=1)


class RoleAssignmentRequest(StrictRequest):
    role: RoleCode


class UserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    display_name: str
    email: str
    is_active: bool
    roles: list[RoleCode]
    created_at: datetime

    @classmethod
    def from_domain(cls, user: User) -> Self:
        return cls(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            is_active=user.is_active,
            roles=sorted(user.roles, key=str),
            created_at=user.created_at,
        )


class AuthenticationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str | None
    token_type: str
    session_kind: SessionKind
    user: UserResponse | None

    @classmethod
    def from_result(cls, result: AuthenticationResult) -> Self:
        return cls(
            access_token=result.tokens.access_token,
            refresh_token=result.tokens.refresh_token,
            token_type=result.tokens.token_type,
            session_kind=SessionKind.USER if result.user is not None else SessionKind.GUEST,
            user=None if result.user is None else UserResponse.from_domain(result.user),
        )
