"""Pure domain objects for M01 access; no framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RoleCode(StrEnum):
    """The six approved reference roles (ETAPA 06 / roles table)."""

    CUSTOMER = "CUSTOMER"
    WAITER = "WAITER"
    CASHIER = "CASHIER"
    ADMIN = "ADMIN"
    KITCHEN = "KITCHEN"
    SUPER_ADMIN = "SUPER_ADMIN"


class SessionKind(StrEnum):
    """Auth session discriminator."""

    USER = "USER"
    GUEST = "GUEST"


@dataclass(frozen=True, slots=True)
class User:
    """Registered customer or staff member."""

    id: UUID
    display_name: str
    email: str
    is_active: bool
    roles: frozenset[RoleCode]
    created_at: datetime

    def has_role(self, role: RoleCode) -> bool:
        """Check role membership; Super Admin always returns True (RN-03)."""
        return RoleCode.SUPER_ADMIN in self.roles or role in self.roles

    def has_any_role(self, *roles: RoleCode) -> bool:
        """Check if user has at least one of the specified roles (RN-03)."""
        if RoleCode.SUPER_ADMIN in self.roles:
            return True
        return bool(self.roles & frozenset(roles))

    @property
    def is_super_admin(self) -> bool:
        """RN-03: Super Admin has all permissions."""
        return RoleCode.SUPER_ADMIN in self.roles


@dataclass(frozen=True, slots=True)
class AuthSession:
    """Registered-user or limited guest session."""

    id: UUID
    kind: SessionKind
    user_id: UUID | None
    renewal_token_hash: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None

    def is_active_at(self, now: datetime) -> bool:
        """Session is active when not revoked and not expired."""
        return self.revoked_at is None and now < self.expires_at


@dataclass(frozen=True, slots=True)
class AuthTokens:
    """Access and refresh tokens returned after successful authentication."""

    access_token: str
    refresh_token: str | None
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded claims from an access token."""

    user_id: UUID | None
    session_id: UUID
    roles: frozenset[RoleCode]
    kind: SessionKind


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated request actor resolved against current database state."""

    user_id: UUID | None
    session_id: UUID
    roles: frozenset[RoleCode]
    kind: SessionKind

    @property
    def is_super_admin(self) -> bool:
        """Super Admin bypasses role restrictions (RF-M01-05 / RN-03)."""

        return RoleCode.SUPER_ADMIN in self.roles

    def has_any_role(self, *required: RoleCode) -> bool:
        """Roles accumulate; a matching role or Super Admin authorizes the actor."""

        return self.is_super_admin or bool(self.roles & frozenset(required))
