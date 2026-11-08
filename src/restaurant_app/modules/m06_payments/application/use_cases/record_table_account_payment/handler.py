"""Record one idempotent payment against the whole table account."""

import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.table_account_repository import (
    TableAccountRepository,
)
from restaurant_app.modules.m06_payments.domain.entities import TableAccountSummary
from restaurant_app.modules.m06_payments.domain.errors import (
    InvalidPaymentRequestError,
    PaymentConflictError,
)
from restaurant_app.modules.m06_payments.domain.payment_methods import validate_collection_method


class RecordTableAccountPayment:
    def __init__(self, accounts: TableAccountRepository) -> None:
        self._accounts = accounts
        self._authorize = AuthorizeRoles(RoleCode.CASHIER)

    async def __call__(
        self,
        *,
        actor: Principal,
        table_id: UUID,
        amount: Decimal,
        method_code: str,
        reference_code: str | None,
        request_key: str,
    ) -> TableAccountSummary:
        self._authorize(actor)
        if actor.user_id is None:
            raise InvalidPaymentRequestError("A staff user is required")
        if not 1 <= len(request_key) <= 128 or request_key.strip() != request_key:
            raise InvalidPaymentRequestError("Invalid Idempotency-Key")
        try:
            cents = amount.quantize(Decimal("0.01"))
        except (InvalidOperation, AttributeError) as error:
            raise InvalidPaymentRequestError("amount must be a valid decimal") from error
        if cents <= 0 or cents != amount:
            raise InvalidPaymentRequestError("amount must be positive with at most two decimals")
        method, reference = validate_collection_method(method_code, reference_code)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "table_id": str(table_id),
                    "amount": str(cents),
                    "method_code": method,
                    "reference_code": reference,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        replay_account_id = await self._accounts.find_request(
            actor_id=actor.user_id, key=request_key, fingerprint=fingerprint
        )
        if replay_account_id is not None:
            return await self._accounts.get_summary(replay_account_id)

        state = await self._accounts.open_account_state(table_id)
        if any(status != "CONFIRMED" for status in state.order_statuses):
            raise PaymentConflictError(
                "All table orders must be confirmed before collecting the account"
            )
        if state.balance <= 0:
            raise PaymentConflictError("The table account is already paid")
        if cents > state.balance:
            raise PaymentConflictError(
                f"Amount {cents} exceeds remaining table balance {state.balance}"
            )
        await self._accounts.record_payment(
            account_id=state.id,
            actor_id=actor.user_id,
            request_key=request_key,
            fingerprint=fingerprint,
            amount=cents,
            method_code=method,
            reference_code=reference,
        )
        if cents == state.balance:
            await self._accounts.settle(
                account_id=state.id,
                order_ids=state.order_ids,
                actor_id=actor.user_id,
            )
        return await self._accounts.get_summary(state.id)
