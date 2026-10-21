"""Register a customer account (RF-M01-01, CA-M01-01-01)."""

from dataclasses import dataclass

from restaurant_app.modules.m01_access.application.ports.password_hasher import (
    PasswordHasher,
)
from restaurant_app.modules.m01_access.application.ports.user_repository import (
    UserRepository,
)
from restaurant_app.modules.m01_access.domain.entities import User
from restaurant_app.modules.m01_access.domain.errors import EmailAlreadyRegisteredError


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    """Validated registration input."""

    display_name: str
    email: str
    password: str


class RegisterUser:
    """Create a CUSTOMER account while keeping cleartext out of persistence."""

    def __init__(self, users: UserRepository, hasher: PasswordHasher) -> None:
        self._users = users
        self._hasher = hasher

    async def __call__(self, command: RegisterUserCommand) -> User:
        normalized_email = command.email.strip().casefold()
        if await self._users.find_by_email_with_hash(normalized_email) is not None:
            raise EmailAlreadyRegisteredError(normalized_email)

        return await self._users.create(
            display_name=command.display_name.strip(),
            email=normalized_email,
            password_hash=self._hasher.hash(command.password),
        )
