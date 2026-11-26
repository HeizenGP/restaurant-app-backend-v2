"""Collect a table balance or selected quantities in a single transaction."""

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m06_payments.application.ports.table_account_repository import TableCheckoutRepository
from restaurant_app.modules.m06_payments.domain.entities import TableAccountSummary
from restaurant_app.modules.m06_payments.domain.errors import InvalidPaymentRequestError, PaymentConflictError
from restaurant_app.modules.m06_payments.domain.payment_methods import validate_collection_method

PaymentLeg = tuple[Decimal, str, str | None]


class RecordTableCheckout:
    def __init__(self, accounts: TableCheckoutRepository) -> None:
        self._accounts = accounts

    async def __call__(
        self, *, actor: Principal, table_id: UUID, account_id: UUID, key: str,
        legs: tuple[PaymentLeg, ...], items: dict[UUID, int],
    ) -> TableAccountSummary:
        AuthorizeRoles(RoleCode.CASHIER)(actor)
        assert actor.user_id is not None
        if not key or key.strip() != key or len(key) > 128:
            raise InvalidPaymentRequestError("Idempotency-Key inválida")
        if not 1 <= len(legs) <= 4:
            raise InvalidPaymentRequestError("Indica de uno a cuatro medios de pago")
        normalized = []
        for amount, method, reference in legs:
            if not amount.is_finite() or not 0 < amount <= Decimal("9999999999.99"):
                raise InvalidPaymentRequestError("Importe inválido")
            cents = amount.quantize(Decimal(".01"))
            if cents != amount:
                raise InvalidPaymentRequestError("El importe admite dos decimales")
            method, reference = validate_collection_method(method, reference)
            normalized.append((cents, method, reference))
        if len({method for _, method, _ in normalized}) != len(normalized):
            raise InvalidPaymentRequestError("Usa un medio distinto para cada parte del cobro")
        fingerprint = hashlib.sha256(json.dumps({
            "table": str(table_id), "account": str(account_id),
            "legs": [(str(amount), method, reference) for amount, method, reference in normalized],
            "items": sorted((str(item), quantity) for item, quantity in items.items()),
        }, separators=(",", ":")).encode()).hexdigest()
        operation = "checkout-" + hashlib.sha256(key.encode()).hexdigest()
        await self._accounts.lock_checkout(f"{actor.user_id}:{operation}")
        replay = await self._accounts.find_request(
            actor_id=actor.user_id, key=f"{operation}-0", fingerprint=fingerprint,
        )
        if replay is not None:
            return await self._accounts.get_summary(replay)

        state = await self._accounts.open_account_state(table_id)
        if state.id != account_id:
            raise PaymentConflictError("La cuenta cambió. Vuelve a abrir el cobro")
        if any(status != "CONFIRMED" for status in state.order_statuses) or state.unserved_order_ids:
            raise PaymentConflictError("Todos los pedidos deben estar listos para cobrar")
        expected = state.balance
        if items:
            summary = await self._accounts.get_summary(account_id)
            if not summary.supports_item_selection:
                raise PaymentConflictError("Esta cuenta tiene cobros previos sin desglose. Cobra el saldo completo")
            available = {line.item_id: line for order in summary.orders for line in order.lines}
            expected = Decimal("0.00")
            for item, quantity in items.items():
                line = available.get(item)
                if line is None or not 0 < quantity <= line.quantity - line.paid_quantity:
                    raise PaymentConflictError("Una cantidad seleccionada ya se cobró o cambió")
                expected += line.unit_price * quantity
        total = sum((amount for amount, _, _ in normalized), Decimal("0.00"))
        if total != expected or total > state.balance:
            raise PaymentConflictError("El importe debe coincidir con la selección y el saldo actual")
        allocation_request_id = None
        for index, (amount, method, reference) in enumerate(normalized):
            request = await self._accounts.record_payment(
                account_id=state.id, actor_id=actor.user_id, request_key=f"{operation}-{index}",
                fingerprint=fingerprint, amount=amount, method_code=method, reference_code=reference,
                allocate_to_items=bool(items) and index == 0, allocation_request_id=allocation_request_id,
            )
            if index == 0 and items:
                await self._accounts.record_allocations(request, items)
                allocation_request_id = request
        if total == state.balance:
            await self._accounts.settle(account_id=state.id, order_ids=state.order_ids, actor_id=actor.user_id)
        return await self._accounts.get_summary(state.id)
