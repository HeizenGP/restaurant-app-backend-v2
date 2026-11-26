"""Port consumed by consolidated table-account use cases."""

from decimal import Decimal
from typing import Protocol
from uuid import UUID

from restaurant_app.modules.m06_payments.domain.entities import (
    TableAccountChargeState,
    TableAccountSummary,
)


class TableAccountRepository(Protocol):
    async def find_request(self, *, actor_id: UUID, key: str, fingerprint: str) -> UUID | None: ...

    async def get_summary_by_table(self, table_id: UUID) -> TableAccountSummary: ...

    async def get_summary(self, account_id: UUID) -> TableAccountSummary: ...

    async def open_account_state(self, table_id: UUID) -> TableAccountChargeState: ...

    async def record_payment(
        self,
        *,
        account_id: UUID,
        actor_id: UUID,
        request_key: str,
        fingerprint: str,
        amount: Decimal,
        method_code: str,
        reference_code: str | None,
        allocate_to_items: bool = False,
        allocation_request_id: UUID | None = None,
    ) -> UUID: ...

    async def settle(
        self,
        *,
        account_id: UUID,
        order_ids: tuple[UUID, ...],
        actor_id: UUID,
    ) -> None: ...


class TableCheckoutRepository(TableAccountRepository, Protocol):
    async def lock_checkout(self, request_key: str) -> None: ...

    async def record_allocations(self, request_id: UUID, items: dict[UUID, int]) -> None: ...
