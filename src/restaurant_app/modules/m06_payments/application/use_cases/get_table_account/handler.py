"""Read the current or most recent account for a table."""

from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.table_account_repository import (
    TableAccountRepository,
)
from restaurant_app.modules.m06_payments.domain.entities import TableAccountSummary


class GetTableAccount:
    def __init__(self, accounts: TableAccountRepository) -> None:
        self._accounts = accounts
        self._authorize = AuthorizeRoles(RoleCode.CASHIER, RoleCode.ADMIN, RoleCode.WAITER)

    async def __call__(self, *, actor: Principal, table_id: UUID) -> TableAccountSummary:
        self._authorize(actor)
        return await self._accounts.get_summary_by_table(table_id)
