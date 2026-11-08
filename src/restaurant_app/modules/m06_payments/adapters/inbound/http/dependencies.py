"""Compose M06 advance and collection handlers on the request-owned session."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_app.modules.m01_access.public import (
    AuthorizeRoles,
    CurrentPrincipal,
    Principal,
    RoleCode,
)
from restaurant_app.modules.m04_orders.public import (
    SqlAlchemyAdvanceOrderReader,
    SqlAlchemyCollectionOrderReader,
)
from restaurant_app.modules.m06_payments.adapters.outbound import (
    SqlAlchemyAdvanceRepository,
    SqlAlchemyCollectionRepository,
)
from restaurant_app.modules.m06_payments.adapters.outbound.table_account_repository import (
    SqlAlchemyTableAccountRepository,
)
from restaurant_app.modules.m06_payments.application.use_cases.get_advance_summary import (
    GetAdvanceSummary,
)
from restaurant_app.modules.m06_payments.application.use_cases.get_payment_summary import (
    GetPaymentSummary,
)
from restaurant_app.modules.m06_payments.application.use_cases.get_table_account import (
    GetTableAccount,
)
from restaurant_app.modules.m06_payments.application.use_cases.record_collection import (
    RecordCollection,
)
from restaurant_app.modules.m06_payments.application.use_cases.record_table_account_payment import (
    RecordTableAccountPayment,
)
from restaurant_app.modules.m06_payments.application.use_cases.verify_advance import VerifyAdvance
from restaurant_app.modules.m07_fulfillment.public import SqlAlchemyHandoverReader

# ---------------------------------------------------------------------------
# Advance handlers (08.05)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Collection / cashier handlers (08.08)
# ---------------------------------------------------------------------------


def record_collection_handler(session: AsyncSession) -> RecordCollection:
    return RecordCollection(
        SqlAlchemyCollectionOrderReader(session),
        SqlAlchemyCollectionRepository(session),
        SqlAlchemyHandoverReader(session),
    )


def get_payment_summary_handler(session: AsyncSession) -> GetPaymentSummary:
    return GetPaymentSummary(
        SqlAlchemyCollectionOrderReader(session),
        SqlAlchemyCollectionRepository(session),
    )


async def require_cashier(actor: CurrentPrincipal) -> Principal:
    AuthorizeRoles(RoleCode.CASHIER)(actor)
    return actor


Cashier = Annotated[Principal, Depends(require_cashier)]


def get_table_account_handler(session: AsyncSession) -> GetTableAccount:
    return GetTableAccount(SqlAlchemyTableAccountRepository(session))


def record_table_account_payment_handler(session: AsyncSession) -> RecordTableAccountPayment:
    return RecordTableAccountPayment(SqlAlchemyTableAccountRepository(session))
