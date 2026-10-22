"""Compose M06 advance handlers on the request-owned SQLAlchemy session."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)
from restaurant_app.modules.m04_orders.public import SqlAlchemyAdvanceOrderReader
from restaurant_app.modules.m06_payments.adapters.outbound import SqlAlchemyAdvanceRepository
from restaurant_app.modules.m06_payments.application.use_cases.get_advance_summary import (
    GetAdvanceSummary,
)
from restaurant_app.modules.m06_payments.application.use_cases.verify_advance import VerifyAdvance


def get_advance_handler(session: AsyncSession) -> GetAdvanceSummary:
    return GetAdvanceSummary(
        SqlAlchemyAdvanceOrderReader(session), SqlAlchemyAdvanceRepository(session)
    )


def verify_advance_handler(session: AsyncSession) -> VerifyAdvance:
    return VerifyAdvance(
        SqlAlchemyAdvanceOrderReader(session), SqlAlchemyAdvanceRepository(session)
    )


async def require_advance_admin(actor: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.ADMIN)(actor)
    return actor


AdvanceAdmin = Annotated[Principal, Depends(require_advance_admin)]
