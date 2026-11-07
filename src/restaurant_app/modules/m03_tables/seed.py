"""Seed initial restaurant tables (RF-M03-01)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger("restaurant_app.tables.seed")

SEED_TABLES_SQL = """
INSERT INTO public.restaurant_tables (id, code, area_label, is_occupied) VALUES
    ('7a000001-0000-4000-a000-000000000001', 'MESA-01', 'Salón Principal', FALSE),
    ('7a000001-0000-4000-a000-000000000002', 'MESA-02', 'Salón Principal', FALSE),
    ('7a000001-0000-4000-a000-000000000003', 'MESA-03', 'Salón Principal', FALSE),
    ('7a000001-0000-4000-a000-000000000004', 'MESA-04', 'Salón Principal', FALSE),
    ('7a000001-0000-4000-a000-000000000005', 'MESA-05', 'Salón Principal', FALSE),
    ('7a000001-0000-4000-a000-000000000006', 'MESA-06', 'Terraza', FALSE),
    ('7a000001-0000-4000-a000-000000000007', 'MESA-07', 'Terraza', FALSE),
    ('7a000001-0000-4000-a000-000000000008', 'MESA-08', 'Terraza', FALSE),
    ('7a000001-0000-4000-a000-000000000009', 'MESA-09', 'Zona VIP', FALSE),
    ('7a000001-0000-4000-a000-000000000010', 'MESA-10', 'Zona VIP', FALSE)
ON CONFLICT (code) DO NOTHING;
"""


async def seed_initial_tables(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Safely seed initial restaurant tables if not already present."""
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text(SEED_TABLES_SQL))
        logger.info("Initial 10 restaurant tables ensured.")
