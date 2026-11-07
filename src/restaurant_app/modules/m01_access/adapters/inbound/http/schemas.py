"""Pydantic HTTP contracts for M01; domain and application stay framework-free."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Self
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

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        password = value.get_secret_value()
        if not any(character.islower() for character in password):
            raise ValueError("password must include a lowercase letter")
        if not any(character.isupper() for character in password):
            raise ValueError("password must include an uppercase letter")
        if not any(character.isdigit() for character in password):
            raise ValueError("password must include a number")
        return value


class LoginRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=128)


class GoogleLoginRequest(StrictRequest):
    id_token: SecretStr = Field(min_length=20, max_length=8192)


class PasswordResetRequest(StrictRequest):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        return RegisterRequest.validate_email_shape(value)


class PasswordResetConfirmRequest(StrictRequest):
    token: SecretStr = Field(min_length=32, max_length=512)
    new_password: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, value: SecretStr) -> SecretStr:
        return RegisterRequest.validate_password_strength(value)


class MessageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: str


class RefreshRequest(StrictRequest):
    refresh_token: SecretStr = Field(min_length=1)


class RoleAssignmentRequest(StrictRequest):
    role: RoleCode


class SavedCardInput(StrictRequest):
    id: str = Field(min_length=1)
    card_number_masked: str = Field(min_length=4, max_length=30)
    card_holder: str = Field(min_length=1, max_length=120)
    expiry: str = Field(min_length=3, max_length=10)
    brand: str = Field(min_length=1, max_length=30)
    document_type: str | None = Field(default=None, max_length=20)
    document_number: str | None = Field(default=None, max_length=30)


class SavedAddressInput(StrictRequest):
    id: str = Field(min_length=1)
    label: str = Field(min_length=1, max_length=50)
    address: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=200)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    department: str | None = Field(default=None, max_length=50)
    recipient_phone: str | None = Field(default=None, max_length=30)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    is_default: bool = False


class CreateAddressRequest(StrictRequest):
    label: str = Field(min_length=1, max_length=50)
    address: str = Field(min_length=3, max_length=500)
    department: str | None = Field(default=None, max_length=50)
    reference: str | None = Field(default=None, max_length=200)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    recipient_phone: str | None = Field(default=None, max_length=30)
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    is_default: bool = False


class UpdateAddressRequest(StrictRequest):
    label: str | None = Field(default=None, min_length=1, max_length=50)
    address: str | None = Field(default=None, min_length=3, max_length=500)
    department: str | None = Field(default=None, max_length=50)
    reference: str | None = Field(default=None, max_length=200)
    delivery_instructions: str | None = Field(default=None, max_length=500)
    recipient_phone: str | None = Field(default=None, max_length=30)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    is_default: bool | None = None


class AddressResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    user_id: UUID
    label: str
    address: str
    department: str | None = None
    reference: str | None = None
    delivery_instructions: str | None = None
    recipient_phone: str | None = None
    latitude: float
    longitude: float
    is_default: bool
    created_at: datetime
    updated_at: datetime


class UpdateProfileRequest(StrictRequest):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = None
    saved_cards: list[SavedCardInput] | None = None
    saved_addresses: list[SavedAddressInput] | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    display_name: str
    email: str
    is_active: bool
    roles: list[RoleCode]
    created_at: datetime
    phone: str | None = None
    avatar_url: str | None = None
    saved_cards: list[dict[str, Any]] = Field(default_factory=list)
    saved_addresses: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, user: User) -> Self:
        return cls(
            id=user.id,
            display_name=user.display_name,
            email=user.email,
            is_active=user.is_active,
            roles=sorted(user.roles, key=str),
            created_at=user.created_at,
            phone=user.phone,
            avatar_url=user.avatar_url,
            saved_cards=list(user.saved_cards),
            saved_addresses=list(user.saved_addresses),
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
