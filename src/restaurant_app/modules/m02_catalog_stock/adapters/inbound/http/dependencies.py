"""M02 composition helpers; M01 is consumed only through its public contract."""

from typing import Annotated

from fastapi import Depends

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)


async def require_catalog_admin(principal: CurrentPrincipal) -> Principal:
    """Reject non-admin callers at the HTTP edge as well as in each handler."""

    AuthorizeRoles(RoleCode.ADMIN)(principal)
    return principal


CatalogAdmin = Annotated[Principal, Depends(require_catalog_admin)]
