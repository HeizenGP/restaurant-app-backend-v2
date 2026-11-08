"""Register immutable APP/manual requests without confirming them (08.04)."""

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from restaurant_app.modules.m01_access.public import AuthorizeRoles, Principal, RoleCode
from restaurant_app.modules.m04_orders.application.ports.order_repository import (
    OrderRepository,
    ProductReader,
    TableOccupancy,
    TableReader,
)
from restaurant_app.modules.m04_orders.domain.entities import (
    Channel,
    Modality,
    Order,
    OrderLine,
    RequestedItem,
)
from restaurant_app.modules.m04_orders.domain.errors import (
    InvalidOrderError,
    ProductUnavailableError,
)


class CreateOrder:
    def __init__(
        self,
        orders: OrderRepository,
        products: ProductReader,
        tables: TableReader,
        waiter_tables: TableOccupancy | None = None,
    ) -> None:
        self._orders = orders
        self._products = products
        self._tables = tables
        self._waiter_tables = waiter_tables
        self._authorize_admin = AuthorizeRoles(RoleCode.ADMIN)

    async def __call__(
        self,
        *,
        actor: Principal,
        request_key: str,
        modality: Modality,
        channel: Channel,
        items: tuple[RequestedItem, ...],
        table_id: UUID | None,
        delivery_address: str | None,
        contact_name: str | None,
        contact_phone: str | None,
    ) -> Order:
        if channel is Channel.APP:
            if actor.kind.value == "USER":
                AuthorizeRoles(RoleCode.CUSTOMER)(actor)
        elif channel is Channel.WAITER:
            AuthorizeRoles(RoleCode.WAITER)(actor)
        else:
            self._authorize_admin(actor)
            if channel not in {Channel.PHONE, Channel.WHATSAPP}:
                raise InvalidOrderError("Unsupported manual channel")
        if not 1 <= len(request_key) <= 128 or not request_key.strip():
            raise InvalidOrderError("Idempotency-Key must contain 1 to 128 characters")
        if (
            not items
            or len(items) > 100
            or any(item.quantity <= 0 or item.quantity > 2_147_483_647 for item in items)
        ):
            raise InvalidOrderError("Order must contain valid positive quantities")
        if len({item.product_id for item in items}) != len(items):
            raise InvalidOrderError("Duplicate products must be consolidated")
        if modality is Modality.LOCAL:
            if (
                channel not in {Channel.APP, Channel.WAITER}
                or table_id is None
                or delivery_address is not None
            ):
                raise InvalidOrderError("Local orders require a table and no delivery address")
        elif modality is Modality.DELIVERY:
            if (
                channel is Channel.WAITER
                or table_id is not None
                or not delivery_address
                or not delivery_address.strip()
            ):
                raise InvalidOrderError("Delivery requires an address and no table")
        elif channel is Channel.WAITER or table_id is not None or delivery_address is not None:
            raise InvalidOrderError("Pickup requires no table or delivery address")
        if modality is not Modality.LOCAL and (not contact_name or not contact_phone):
            raise InvalidOrderError("Pickup and delivery require contact name and phone")
        if (
            (contact_name is not None and len(contact_name) > 120)
            or (contact_phone is not None and len(contact_phone) > 30)
            or (delivery_address is not None and len(delivery_address) > 1000)
        ):
            raise InvalidOrderError("Order contact or address exceeds its allowed length")
        actor_id = actor.user_id or actor.session_id
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "modality": modality,
                    "channel": channel,
                    "items": sorted((str(item.product_id), item.quantity) for item in items),
                    "table_id": str(table_id) if table_id else None,
                    "delivery_address": delivery_address,
                    "contact_name": contact_name,
                    "contact_phone": contact_phone,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        replay = await self._orders.find_request(
            actor_id=actor_id, key=request_key, fingerprint=fingerprint
        )
        if replay is not None:
            return replay
        if table_id is not None:
            if channel is Channel.WAITER:
                assert self._waiter_tables is not None and actor.user_id is not None
                table = await self._waiter_tables.lock_table(table_id)
                if table is None:
                    raise InvalidOrderError("Table not found")
                if not table.is_occupied:
                    await self._waiter_tables.occupy(table_id, actor_id=actor.user_id)
            else:
                table = (
                    await self._waiter_tables.lock_table(table_id)
                    if self._waiter_tables is not None
                    else await self._tables.get_table(table_id)
                )
                if table is None:
                    raise InvalidOrderError("Table not found")
                if table.is_occupied:
                    if (
                        table.occupancy_started_at is None
                        or not await self._orders.has_verified_active_table_order(
                            table_id=table_id,
                            occupied_since=table.occupancy_started_at,
                            customer_user_id=actor.user_id,
                            guest_session_id=actor.session_id if actor.user_id is None else None,
                        )
                    ):
                        raise InvalidOrderError("The selected table is occupied")
                elif self._waiter_tables is not None:
                    await self._waiter_tables.occupy(table_id, actor_id=actor.user_id)
        lines: list[OrderLine] = []
        total = Decimal("0.00")
        for item in sorted(items, key=lambda line: line.product_id):
            product = await self._products.get_product(item.product_id)
            if product is None or not product.is_available:
                raise ProductUnavailableError("Product is unavailable for a new request")
            line_total = product.price * item.quantity
            total += line_total
            lines.append(
                OrderLine(
                    product_id=product.id,
                    product_name_snapshot=product.name,
                    quantity=item.quantity,
                    unit_price_snapshot=product.price,
                )
            )
        if total <= 0 or total > Decimal("9999999999.99"):
            raise InvalidOrderError(
                "Order total must be positive and fit the approved currency field"
            )
        return await self._orders.create_order(
            actor_id=actor_id,
            request_key=request_key,
            fingerprint=fingerprint,
            modality=modality,
            channel=channel,
            customer_user_id=actor.user_id if channel is Channel.APP else None,
            guest_session_id=actor.session_id
            if channel is Channel.APP and actor.user_id is None
            else None,
            created_by_user_id=actor.user_id if channel is not Channel.APP else None,
            table_id=table_id,
            delivery_address=delivery_address,
            contact_name=contact_name,
            contact_phone=contact_phone,
            lines=tuple(lines),
        )
