"""HTTP role guards for table administration and staff occupancy."""

from typing import Annotated

from fastapi import Depends

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)


async def require_table_staff(principal: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.WAITER, RoleCode.ADMIN)(principal)
    return principal


async def require_table_admin(principal: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.ADMIN)(principal)
    return principal


TableStaff = Annotated[Principal, Depends(require_table_staff)]
TableAdmin = Annotated[Principal, Depends(require_table_admin)]
