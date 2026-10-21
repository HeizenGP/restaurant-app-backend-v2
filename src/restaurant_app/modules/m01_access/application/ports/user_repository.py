"""Port for user persistence; implemented by outbound adapters."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m01_access.domain.entities import RoleCode, User


class UserRepository(Protocol):
    """Contract consumed by M01 use cases; adapters own the implementation."""

    async def find_by_email_with_hash(self, email: str) -> tuple[User, str] | None:
        """Return ``(user, password_hash)`` or *None* if not found."""
        ...

    async def find_by_id(self, user_id: UUID) -> User | None:
        """Return user with roles loaded, or *None*."""
        ...

    async def create(
        self,
        *,
        display_name: str,
        email: str,
        password_hash: str,
    ) -> User:
        """Create a new user with the CUSTOMER role and return it."""
        ...

    async def assign_role(self, user_id: UUID, role_code: RoleCode) -> None:
        """Add *role_code* to the user's role set."""
        ...

    async def has_role(self, user_id: UUID, role_code: RoleCode) -> bool:
        """Check if the user has a specific role assignment."""
        ...
