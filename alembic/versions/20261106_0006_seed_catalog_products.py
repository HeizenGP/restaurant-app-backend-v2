"""Seed initial catalog categories and products for Chifa ASIA.

Revision ID: 20261106_0006
Revises: 20261029_0005
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261106_0006"
down_revision: str | Sequence[str] | None = "20261029_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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

PRODUCT_IDS = (
    "b0010001-0000-4000-a000-000000000001",
    "b0010001-0000-4000-a000-000000000002",
    "b0010001-0000-4000-a000-000000000003",
    "b0010001-0000-4000-a000-000000000004",
    "b0010001-0000-4000-a000-000000000005",
    "b0010002-0000-4000-a000-000000000001",
    "b0010002-0000-4000-a000-000000000002",
    "b0010002-0000-4000-a000-000000000003",
    "b0010002-0000-4000-a000-000000000004",
    "b0010003-0000-4000-a000-000000000001",
    "b0010003-0000-4000-a000-000000000002",
    "b0010003-0000-4000-a000-000000000003",
    "b0010003-0000-4000-a000-000000000004",
    "b0010004-0000-4000-a000-000000000001",
    "b0010004-0000-4000-a000-000000000002",
    "b0010004-0000-4000-a000-000000000003",
    "b0010004-0000-4000-a000-000000000004",
    "b0010005-0000-4000-a000-000000000001",
    "b0010005-0000-4000-a000-000000000002",
    "b0010005-0000-4000-a000-000000000003",
    "b0010005-0000-4000-a000-000000000004",
)

CATEGORY_IDS = (
    "ca700001-0000-4000-a000-000000000001",
    "ca700001-0000-4000-a000-000000000002",
    "ca700001-0000-4000-a000-000000000003",
    "ca700001-0000-4000-a000-000000000004",
    "ca700001-0000-4000-a000-000000000005",
)


def upgrade() -> None:
    op.execute(SEED_CATEGORIES_SQL)
    op.execute(SEED_PRODUCTS_SQL)


def downgrade() -> None:
    ids_p = ", ".join(f"'{i}'" for i in PRODUCT_IDS)
    ids_c = ", ".join(f"'{i}'" for i in CATEGORY_IDS)
    op.execute(f"DELETE FROM public.products WHERE id IN ({ids_p})")
    op.execute(f"DELETE FROM public.categories WHERE id IN ({ids_c})")
