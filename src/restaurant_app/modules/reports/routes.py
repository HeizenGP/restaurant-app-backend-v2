"""Reports and KPIs endpoint for KAIRO Admin Dashboard."""

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from restaurant_app.core.dependencies import DatabaseSession
from restaurant_app.modules.m01_access.adapters.inbound.http.dependencies import AdminPrincipal
from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import ProductModel
from restaurant_app.modules.m03_tables.adapters.outbound.models import RestaurantTableModel
from restaurant_app.modules.m04_orders.adapters.outbound.models import OrderItemModel, OrderModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


class TopProductStat(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    total_quantity: int


class DashboardOrderSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    modality: str
    channel: str
    status: str
    total_amount: float
    created_at: str
    contact_name: str | None = None
    table_id: str | None = None


class DashboardStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    today_sales: float
    today_orders_count: int
    active_orders_count: int
    occupied_tables_count: int
    total_tables_count: int
    total_products_count: int
    low_stock_count: int
    orders_by_modality: dict[str, int]
    orders_by_status: dict[str, int]
    top_products: list[TopProductStat]
    recent_orders: list[DashboardOrderSummary]


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    actor: AdminPrincipal,
    session: DatabaseSession,
) -> DashboardStatsResponse:
    now = datetime.now(UTC)
    today_start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    # 1. Total sales today (sum of collections)
    today_sales_query = select(func.coalesce(func.sum(PaymentModel.amount), Decimal("0"))).where(
        PaymentModel.kind == "COLLECTION",
        PaymentModel.recorded_at >= today_start,
    )
    today_sales_val = await session.scalar(today_sales_query) or Decimal("0")

    # 2. Total orders created today
    today_orders_query = select(func.count(OrderModel.id)).where(
        OrderModel.created_at >= today_start
    )
    today_orders_count = await session.scalar(today_orders_query) or 0

    # 3. Active orders count (REQUESTED, APPROVED, CONFIRMED)
    active_orders_query = select(func.count(OrderModel.id)).where(
        OrderModel.status.in_(["REQUESTED", "APPROVED", "CONFIRMED"])
    )
    active_orders_count = await session.scalar(active_orders_query) or 0

    # 4. Tables count & occupancy
    total_tables_query = select(func.count(RestaurantTableModel.id))
    total_tables_count = await session.scalar(total_tables_query) or 0

    occupied_tables_query = select(func.count(RestaurantTableModel.id)).where(
        RestaurantTableModel.is_occupied.is_(True)
    )
    occupied_tables_count = await session.scalar(occupied_tables_query) or 0

    # 5. Products count & low stock (< 10)
    total_products_query = select(func.count(ProductModel.id))
    total_products_count = await session.scalar(total_products_query) or 0

    low_stock_query = select(func.count(ProductModel.id)).where(ProductModel.stock_qty <= 10)
    low_stock_count = await session.scalar(low_stock_query) or 0

    # 6. Orders by modality
    modality_rows = (
        await session.execute(
            select(OrderModel.modality, func.count(OrderModel.id)).group_by(OrderModel.modality)
        )
    ).all()
    orders_by_modality = {str(row[0]): int(row[1]) for row in modality_rows}

    # 7. Orders by status
    status_rows = (
        await session.execute(
            select(OrderModel.status, func.count(OrderModel.id)).group_by(OrderModel.status)
        )
    ).all()
    orders_by_status = {str(row[0]): int(row[1]) for row in status_rows}

    # 8. Top 5 selling products
    top_rows = (
        await session.execute(
            select(OrderItemModel.product_name_snapshot, func.sum(OrderItemModel.quantity))
            .group_by(OrderItemModel.product_name_snapshot)
            .order_by(func.sum(OrderItemModel.quantity).desc())
            .limit(5)
        )
    ).all()
    top_products = [
        TopProductStat(name=str(row[0]), total_quantity=int(row[1])) for row in top_rows
    ]

    # 9. Recent 10 orders
    recent_rows = (
        await session.scalars(select(OrderModel).order_by(OrderModel.created_at.desc()).limit(10))
    ).all()
    recent_orders = [
        DashboardOrderSummary(
            id=str(o.id),
            modality=o.modality,
            channel=o.channel,
            status=o.status,
            total_amount=float(o.total_amount),
            created_at=o.created_at.isoformat(),
            contact_name=o.contact_name,
            table_id=str(o.table_id) if o.table_id else None,
        )
        for o in recent_rows
    ]

    return DashboardStatsResponse(
        today_sales=float(today_sales_val),
        today_orders_count=today_orders_count,
        active_orders_count=active_orders_count,
        occupied_tables_count=occupied_tables_count,
        total_tables_count=total_tables_count,
        total_products_count=total_products_count,
        low_stock_count=low_stock_count,
        orders_by_modality=orders_by_modality,
        orders_by_status=orders_by_status,
        top_products=top_products,
        recent_orders=recent_orders,
    )
