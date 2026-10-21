"""Import registry for Alembic; mappings remain owned by their adapters."""

from restaurant_app.modules.m01_access.adapters.outbound.models import (
    AuthSessionModel,
    RoleModel,
    UserModel,
    UserRoleModel,
)
from restaurant_app.modules.m02_catalog_stock.adapters.outbound.models import (
    CategoryModel,
    ProductModel,
    StockMovementModel,
)
from restaurant_app.modules.m03_tables.adapters.outbound.models import (
    RestaurantTableModel,
)
from restaurant_app.modules.m04_orders.adapters.outbound.models import (
    OrderItemModel,
    OrderModel,
)
from restaurant_app.modules.m05_kitchen.adapters.outbound.models import KitchenTicketModel
from restaurant_app.modules.m06_payments.adapters.outbound.models import PaymentModel
from restaurant_app.modules.m07_fulfillment.adapters.outbound.models import (
    FulfillmentModel,
)
from restaurant_app.shared.adapters.outbound.models import IdempotencyRequestModel

__all__ = [
    "AuthSessionModel",
    "CategoryModel",
    "FulfillmentModel",
    "IdempotencyRequestModel",
    "KitchenTicketModel",
    "OrderItemModel",
    "OrderModel",
    "PaymentModel",
    "ProductModel",
    "RestaurantTableModel",
    "RoleModel",
    "StockMovementModel",
    "UserModel",
    "UserRoleModel",
]
