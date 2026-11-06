"""Seed data and idempotent startup loader for Chifa ASIA catalog."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("restaurant_app.catalog.seed")

SEED_CATEGORIES_SQL = """
INSERT INTO public.categories (id, name) VALUES
    ('ca700001-0000-4000-a000-000000000001', 'Arroces y Chaufas'),
    ('ca700001-0000-4000-a000-000000000002', 'Tallarines y Saltados'),
    ('ca700001-0000-4000-a000-000000000003', 'Sopas y Entradas'),
    ('ca700001-0000-4000-a000-000000000004', 'Especialidades'),
    ('ca700001-0000-4000-a000-000000000005', 'Bebidas')
ON CONFLICT (name) DO NOTHING;
"""

SEED_PRODUCTS_SQL = """
INSERT INTO public.products (id, category_id, name, price, stock_qty, is_available)
SELECT
    v.id,
    c.id,
    v.name,
    v.price,
    v.stock_qty,
    v.is_available
FROM (VALUES
    ('b0010001-0000-4000-a000-000000000001'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa Especial', 24.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000002'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Pollo', 18.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000003'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Carne', 20.00, 50, TRUE),
    ('b0010001-0000-4000-a000-000000000004'::uuid, 'Arroces y Chaufas', 'Aeropuerto Especial', 25.00, 40, TRUE),
    ('b0010001-0000-4000-a000-000000000005'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Chancho', 20.00, 40, TRUE),
    ('b0010002-0000-4000-a000-000000000001'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Pollo', 19.00, 45, TRUE),
    ('b0010002-0000-4000-a000-000000000002'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Carne', 22.00, 45, TRUE),
    ('b0010002-0000-4000-a000-000000000003'::uuid, 'Tallarines y Saltados', 'Tallarín Taypa Especial', 26.00, 35, TRUE),
    ('b0010002-0000-4000-a000-000000000004'::uuid, 'Tallarines y Saltados', 'Tallarín Sam Si', 24.00, 35, TRUE),
    ('b0010003-0000-4000-a000-000000000001'::uuid, 'Sopas y Entradas', 'Sopa Wantán Especial', 18.00, 30, TRUE),
    ('b0010003-0000-4000-a000-000000000002'::uuid, 'Sopas y Entradas', 'Sopa Fuchifú', 16.00, 30, TRUE),
    ('b0010003-0000-4000-a000-000000000003'::uuid, 'Sopas y Entradas', 'Wantán Frito con Salsa Tamarindo (12 un.)', 14.00, 60, TRUE),
    ('b0010003-0000-4000-a000-000000000004'::uuid, 'Sopas y Entradas', 'Siomay al Vapor (6 un.)', 16.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000001'::uuid, 'Especialidades', 'Pollo Chi Jau Kay', 23.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000002'::uuid, 'Especialidades', 'Pollo Ti Pa Kay', 23.00, 40, TRUE),
    ('b0010004-0000-4000-a000-000000000003'::uuid, 'Especialidades', 'Kam Lu Wantán', 27.00, 35, TRUE),
    ('b0010004-0000-4000-a000-000000000004'::uuid, 'Especialidades', 'Chancho con Piña', 24.00, 35, TRUE),
    ('b0010005-0000-4000-a000-000000000001'::uuid, 'Bebidas', 'Chicha Morada Clásica (1L)', 10.00, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000002'::uuid, 'Bebidas', 'Inca Kola 500ml', 4.50, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000003'::uuid, 'Bebidas', 'Coca Cola 500ml', 4.50, 100, TRUE),
    ('b0010005-0000-4000-a000-000000000004'::uuid, 'Bebidas', 'Té Jazmín Caliente', 5.00, 80, TRUE)
) AS v(id, category_name, name, price, stock_qty, is_available)
JOIN public.categories c ON c.name = v.category_name
WHERE NOT EXISTS (
    SELECT 1 FROM public.products p WHERE p.id = v.id OR p.name = v.name
);
"""


async def seed_initial_catalog(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Safely seed initial categories and products if not already present."""
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text(SEED_CATEGORIES_SQL))
            await session.execute(text(SEED_PRODUCTS_SQL))
        logger.info("Initial catalog categories and products ensured.")
