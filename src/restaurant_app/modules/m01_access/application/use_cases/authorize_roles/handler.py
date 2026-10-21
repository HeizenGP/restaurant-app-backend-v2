"""Reusable server-side role guard (RF-M01-03..05)."""

from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind
from restaurant_app.modules.m01_access.domain.errors import AuthorizationError


class AuthorizeRoles:
    """Apply cumulative roles and the Super Admin bypass inside application handlers."""

    def __init__(self, *required_roles: RoleCode) -> None:
        if not required_roles:
            raise ValueError("at least one required role must be declared")
        self._required_roles = required_roles

    def __call__(self, principal: Principal) -> None:
        if principal.kind is not SessionKind.USER or not principal.has_any_role(
            *self._required_roles
        ):
            raise AuthorizationError
