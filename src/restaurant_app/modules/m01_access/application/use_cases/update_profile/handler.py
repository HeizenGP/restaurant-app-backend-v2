"""Update user profile information (phone, avatar, addresses, cards)."""

from uuid import UUID

from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.domain.entities import User


class UpdateUserProfile:
    """Update profile fields for an authenticated user."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def __call__(
        self,
        user_id: UUID,
        *,
        display_name: str | None = None,
        phone: str | None = None,
        avatar_url: str | None = None,
        saved_cards: list[dict] | None = None,
        saved_addresses: list[dict] | None = None,
    ) -> User:
        return await self._users.update_profile(
            user_id,
            display_name=display_name,
            phone=phone,
            avatar_url=avatar_url,
            saved_cards=saved_cards,
            saved_addresses=saved_addresses,
        )

