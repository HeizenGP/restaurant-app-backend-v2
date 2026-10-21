"""Stable in-process contracts exported by M01 to later backend slices."""

from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import CurrentPrincipal
from restaurant_app.modules.m01_access.application.use_cases.authorize_roles import AuthorizeRoles
from restaurant_app.modules.m01_access.domain.entities import Principal, RoleCode, SessionKind

__all__ = ["AuthorizeRoles", "CurrentPrincipal", "Principal", "RoleCode", "SessionKind"]
