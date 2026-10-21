"""Pure M02 catalog values; stock is a finished-product quantity."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Category:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class Product:
    id: UUID
    category_id: UUID
    name: str
    price: Decimal
    stock_qty: int
    is_available: bool
