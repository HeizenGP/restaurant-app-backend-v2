"""Recent operational alerts for the administrator's notification preferences."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import literal, select, union_all

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import AdminPrincipal
from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import ProductModel, StockMovementModel
from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderModel
from restaurant_app.modules.m05_kitchen.adapters.outbound.models import KitchenTicketModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import CashShiftModel

router = APIRouter(prefix="/administration", tags=["Administration"])
Topic = Literal["new_orders", "order_status", "kitchen", "inventory", "cash"]


class OperationalAlert(BaseModel):
    topic: Topic
    resource_id: UUID
    recorded_at: datetime
    message: str


@router.get("/notifications")
async def list_notifications(actor: AdminPrincipal, session: DatabaseSession) -> list[OperationalAlert]:
    since = datetime.now(UTC) - timedelta(days=2)
    orders = OrderModel
    tickets = KitchenTicketModel

    def entry(topic, resource, when, message):
        return select(
            literal(topic).label("topic"), resource.label("resource_id"),
            when.label("recorded_at"), message.label("message"),
        ).where(when >= since)

    alerts = union_all(
        entry("new_orders", orders.id, orders.created_at, literal("Nuevo pedido")),
        entry("order_status", orders.id, orders.decided_at, literal("Pedido revisado")),
        entry("order_status", orders.id, orders.closed_at, literal("Pedido cerrado")),
        entry("kitchen", tickets.order_id, tickets.ready_at, literal("Comanda lista")),
        entry("inventory", ProductModel.id, StockMovementModel.recorded_at, literal("Stock bajo: ").concat(ProductModel.name))
        .join(StockMovementModel, StockMovementModel.product_id == ProductModel.id)
        .where(ProductModel.stock_qty <= ProductModel.minimum_stock, StockMovementModel.quantity_delta < 0),
        entry("cash", CashShiftModel.id, CashShiftModel.opened_at, literal("Apertura de caja")),
        entry("cash", CashShiftModel.id, CashShiftModel.closed_at, literal("Cierre de caja")),
    ).subquery()
    rows = await session.execute(select(alerts).order_by(alerts.c.recorded_at.desc()).limit(100))
    return [OperationalAlert.model_validate(row) for row in rows.mappings()]
