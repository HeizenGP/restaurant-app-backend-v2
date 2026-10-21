"""Assign one cumulative role to a user (RF-M01-04)."""

from uuid import UUID

from restaurant_app.modules.m01_access.application.ports.user_repository import UserRepository
from restaurant_app.modules.m01_access.application.use_cases.authorize_roles import AuthorizeRoles
from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, User
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError, UserNotFoundError


class AssignUserRole:
    """Authorize in the handler before modifying a user's cumulative role set."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users
        self._authorize_admin = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self,
        *,
        actor: Principal,
        user_id: UUID,
        role: RoleCode,
    ) -> User:
        self._authorize_admin(actor)
        if role is RoleCode.SUPER_ADMIN and not actor.is_super_admin:
            raise AuthorizationError("Only a Super Admin can grant the Super Admin role")
        if await self._users.find_by_id(user_id) is None:
            raise UserNotFoundError(str(user_id))
        return await self._users.assign_role(user_id, role)
