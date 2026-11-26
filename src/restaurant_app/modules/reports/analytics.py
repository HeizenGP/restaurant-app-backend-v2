"""Admin analytics derived from operational records over an explicit date range."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import String, cast, func, select

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import AdminPrincipal
from restaurant_app.modules.m01_access.adapters.outbound.models import UserModel
from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import ProductModel, StockMovementModel
from restaurant_app.modules.m03_tables.adapters.outbound.models import RestaurantTableModel, TableAccountModel
from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.reports.routes import router

Report = Literal["sales", "orders", "products", "occupancy", "inventory", "staff"]
Numeric = int | Decimal
LIMA = ZoneInfo("America/Lima")


class Series(BaseModel):
    title: str
    values: dict[str, Numeric]


class AnalyticsResponse(BaseModel):
    metrics: dict[str, Numeric]
    series: list[Series]


@router.get("/analytics/{report}")
async def get_analytics(
    report: Report, start: date, end: date, actor: AdminPrincipal, session: DatabaseSession
) -> AnalyticsResponse:
    if start.year < 2000 or end < start or end >= date.max or end - start > timedelta(days=365):
        raise HTTPException(422, "Selecciona un periodo de hasta 366 días")
    begin = datetime.combine(start, time.min, LIMA).astimezone(UTC)
    stop = datetime.combine(end + timedelta(days=1), time.min, LIMA).astimezone(UTC)

    def during(column):
        return (column >= begin, column < stop)

    async def series(title, statement) -> Series:
        values = {str(key): value for key, value in (await session.execute(statement)).tuples()}
        return Series(title=title, values=values)

    metrics: dict[str, Numeric] = {}
    groups = []
    if report == "sales":
        timestamp = PaymentModel.recorded_at
        amount = PaymentModel.amount
        scope = (PaymentModel.kind == "COLLECTION", *during(timestamp))
        total, count = (await session.execute(
            select(func.coalesce(func.sum(amount), 0), func.count()).where(*scope)
        )).one()
        previous = await session.scalar(
            select(func.coalesce(func.sum(amount), 0)).where(
                PaymentModel.kind == "COLLECTION", timestamp >= begin - (stop - begin), timestamp < begin
            )
        )
        metrics = {"Cobros (S/)": total, "Periodo anterior (S/)": previous, "Transacciones": count}
        if count:
            metrics["Importe medio por transacción (S/)"] = (total / count).quantize(Decimal(".01"))
        day = func.date(func.timezone("America/Lima", timestamp))
        groups = [
            await series("Cobros por día (S/)", select(day, func.sum(amount)).where(*scope).group_by(day).order_by(day)),
            await series("Cobros por método (S/)", select(PaymentModel.method_code, func.sum(amount)).where(*scope).group_by(PaymentModel.method_code)),
        ]
    elif report == "orders":
        scope = during(OrderModel.created_at)
        metrics["Pedidos"] = await session.scalar(select(func.count()).select_from(OrderModel).where(*scope))
        for title, column in (("Pedidos por modalidad", OrderModel.modality), ("Pedidos por estado", OrderModel.status)):
            groups.append(await series(title, select(column, func.count()).where(*scope).group_by(column)))
    elif report == "products":
        item = OrderItemModel
        units = func.sum(item.quantity)
        booked = (
            select(item.product_name_snapshot)
            .join(OrderModel, OrderModel.id == item.order_id)
            .where(OrderModel.status == "CLOSED", *during(OrderModel.closed_at))
            .group_by(item.product_name_snapshot).order_by(units.desc(), item.product_name_snapshot).limit(30)
        )
        groups = [
            await series("Unidades en pedidos cerrados", booked.add_columns(units)),
            await series("Importe de productos en pedidos cerrados (S/)", booked.add_columns(func.sum(item.quantity * item.unit_price_snapshot))),
        ]
    elif report == "occupancy":
        tables, occupied = (await session.execute(
            select(func.count(), func.count().filter(RestaurantTableModel.is_occupied.is_(True))).select_from(RestaurantTableModel)
        )).one()
        metrics = {"Mesas disponibles en el salón": tables, "Mesas ocupadas ahora": occupied}
        if tables:
            metrics["Ocupación actual (%)"] = (Decimal(occupied * 100) / tables).quantize(Decimal(".1"))
        account = TableAccountModel
        hour = func.extract("hour", func.timezone("America/Lima", account.opened_at))
        groups = [
            await series("Cuentas abiertas por hora de Lima", select(hour, func.count()).where(*during(account.opened_at)).group_by(hour).order_by(hour)),
            await series("Cuentas cerradas por mesa", select(RestaurantTableModel.code, func.count()).join(account, account.table_id == RestaurantTableModel.id).where(*during(account.closed_at)).group_by(RestaurantTableModel.code)),
        ]
        average = await session.scalar(select(func.avg(func.extract("epoch", account.closed_at - account.opened_at) / 60)).where(*during(account.closed_at)))
        if average is not None:
            metrics["Duración media de cuentas cerradas (min)"] = Decimal(average).quantize(Decimal(".1"))
    elif report == "inventory":
        zero, low = (await session.execute(
            select(func.count().filter(ProductModel.stock_qty == 0), func.count().filter((ProductModel.stock_qty > 0) & (ProductModel.stock_qty <= ProductModel.minimum_stock))).select_from(ProductModel)
        )).one()
        metrics = {"Agotados actualmente": zero, "Stock bajo actualmente": low}
        move = StockMovementModel
        scope = during(move.recorded_at)
        groups = [
            await series("Movimientos por tipo", select(move.kind, func.count()).where(*scope).group_by(move.kind)),
            await series("Unidades descontadas por producto", select(ProductModel.name, -func.sum(move.quantity_delta)).join(move, move.product_id == ProductModel.id).where(move.quantity_delta < 0, *scope).group_by(ProductModel.name).order_by(func.sum(move.quantity_delta)).limit(30)),
        ]
    else:
        # Group by identifiers so collaborators with identical display names stay distinct.
        name = UserModel.display_name.concat(" · ").concat(func.left(cast(UserModel.id, String), 8))
        groups = [
            await series("Cobros por cajero", select(name, func.count()).join(PaymentModel, PaymentModel.recorded_by_user_id == UserModel.id).where(PaymentModel.kind == "COLLECTION", *during(PaymentModel.recorded_at)).group_by(UserModel.id)),
            await series("Pedidos cerrados por colaborador", select(name, func.count()).join(OrderModel, OrderModel.closed_by_user_id == UserModel.id).where(*during(OrderModel.closed_at)).group_by(UserModel.id)),
        ]
    return AnalyticsResponse(metrics=metrics, series=groups)
