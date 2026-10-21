"""Register a new customer account (RF-M01-01, CA-M01-01-01)."""

from __future__ import annotations

from dataclasses import dataclass

from restaurant_app.modules.m01_access.application.ports.password_hasher import (
    PasswordHasher,
)
from restaurant_app.modules.m01_access.application.ports.user_repository import (
    UserRepository,
)
from restaurant_app.modules.m01_access.domain.entities import User
from restaurant_app.modules.m01_access.domain.errors import (
    EmailAlreadyRegisteredError,
)


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    """Input for user registration."""

    display_name: str
    email: str
    password: str


class RegisterUser:
    """Create a customer account with hashed password (RNF-02)."""

    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
    ) -> None:
        self._users = users
        self._hasher = hasher

    async def __call__(self, command: RegisterUserCommand) -> User:
        existing = await self._users.find_by_email_with_hash(command.email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(command.email)

        password_hash = self._hasher.hash(command.password)
        return await self._users.create(
            display_name=command.display_name,
            email=command.email,
            password_hash=password_hash,
        )
