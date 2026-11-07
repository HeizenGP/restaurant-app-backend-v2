"""Port for user persistence; implemented by outbound adapters."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from restaurant_app.modules.m01_access.domain.entities import RoleCode, User


class UserRepository(Protocol):
    """Contract consumed by M01 use cases; adapters own the implementation."""

    async def find_by_email_with_hash(self, email: str) -> tuple[User, str | None] | None:
        """Return ``(user, password_hash)`` or *None* if not found."""
        ...

    async def find_by_google_subject(self, subject: str) -> User | None:
        """Return the user bound to Google's stable ``sub`` claim."""
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

    async def create_from_google(
        self,
        *,
        display_name: str,
        email: str,
        google_subject: str,
        avatar_url: str | None,
    ) -> User:
        """Create a passwordless CUSTOMER account bound to Google."""
        ...

    async def update_password(self, user_id: UUID, *, password_hash: str) -> None:
        """Set a new local password for an existing account."""
        ...

    async def assign_role(self, user_id: UUID, role_code: RoleCode) -> User:
        """Add *role_code* and return the user with the cumulative role set."""
        ...

    async def update_profile(
        self,
        user_id: UUID,
        *,
        display_name: str | None = None,
        phone: str | None = None,
        avatar_url: str | None = None,
        saved_cards: list[dict[str, Any]] | None = None,
        saved_addresses: list[dict[str, Any]] | None = None,
    ) -> User:
        """Update profile fields for *user_id* and return updated user."""
        ...
