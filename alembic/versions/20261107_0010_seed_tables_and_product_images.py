"""Add image_url and description to products, seed 10 tables and catalog images.

Revision ID: 20261107_0010
Revises: 20261107_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0010"
down_revision: str | Sequence[str] | None = "20261107_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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

UPDATE_PRODUCT_IMAGES_SQL = """
UPDATE public.products AS p
SET
    image_url = v.image_url,
    description = v.description
FROM (VALUES
    ('Arroz Chaufa Especial',
     'https://images.unsplash.com/photo-1512058564366-18510be2db19?w=800&auto=format&fit=crop&q=80',
     'Clásico arroz chaufa al wok con pollo en trozos, lomo, chancho asado, langostinos, cebollita china y tortilla de huevo con toque secreto de sillao oscuro.'),
    ('Arroz Chaufa de Pollo',
     'https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=800&auto=format&fit=crop&q=80',
     'Arroz salteado al wok a fuego vivo con tiernos cubos de pollo, huevo, cebollita china fresca y aceite de ajonjolí tostado.'),
    ('Arroz Chaufa de Carne',
     'https://images.unsplash.com/photo-1543339308-43e59d6b73a6?w=800&auto=format&fit=crop&q=80',
     'Sabroso chaufa tradicional salteado al wok con jugosos trozos de lomo de res, brotes de soya y cebolla china.'),
    ('Aeropuerto Especial',
     'https://images.unsplash.com/photo-1552611052-33e04de081de?w=800&auto=format&fit=crop&q=80',
     'Fusión contundente de arroz chaufa y fideo tallarín salteados al wok con pollo, carne, frejolito chino y huevo montado.'),
    ('Arroz Chaufa de Chancho',
     'https://images.unsplash.com/photo-1569058242253-92a9c755a0ec?w=800&auto=format&fit=crop&q=80',
     'Arroz chaufa con chancho laqueado dulce y aromático al estilo oriental con cebollita china crocante.'),
    ('Tallarín Saltado de Pollo',
     'https://images.unsplash.com/photo-1585032226651-759b368d7246?w=800&auto=format&fit=crop&q=80',
     'Tallarines chinos salteados al wok con pechuga de pollo, pimiento rojo, holantao, col china y salsa de ostión.'),
    ('Tallarín Saltado de Carne',
     'https://images.unsplash.com/photo-1617093727343-374698b1b08d?w=800&auto=format&fit=crop&q=80',
     'Fideos gruesos salteados a fuego vivo con finas láminas de lomo de res, cebolla morada, tomate y salsa de soya.'),
    ('Tallarín Taypa Especial',
     'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=800&auto=format&fit=crop&q=80',
     'El rey de la casa: tallarines bañados en salsa especial con pollo, carne, chancho, langostinos, champiñones y verduras selectas.'),
    ('Tallarín Sam Si',
     'https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=800&auto=format&fit=crop&q=80',
     'Tallarines salteados con tiras de tres carnes seleccionadas: pollo, lomo y chancho con crujientes verduras orientales.'),
    ('Sopa Wantán Especial',
     'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=800&auto=format&fit=crop&q=80',
     'Caldo dorado y reconfortante de ave con wantanes rellenos de cerdo y langostino, pollo en láminas, chancho asado y col china.'),
    ('Sopa Fuchifú',
     'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800&auto=format&fit=crop&q=80',
     'Sopa espesada con clara de huevo hilada, trocitos de pechuga de pollo, champiñones y fideos de arroz en caldo aromático con kión.'),
    ('Wantán Frito con Salsa Tamarindo (12 un.)',
     'https://images.unsplash.com/photo-1496116218417-1a781b1c416c?w=800&auto=format&fit=crop&q=80',
     'Docena de crocantes wantanes dorados rellenos de pasta de carne, acompañados de salsa de tamarindo agridulce artesanal.'),
    ('Siomay al Vapor (6 un.)',
     'https://images.unsplash.com/photo-1541696432-82c6da8ce7bf?w=800&auto=format&fit=crop&q=80',
     'Bocaditos dim sum al vapor rellenos de carne de cerdo sazonada con kión, cebolla china y toque de ajonjolí.'),
    ('Pollo Chi Jau Kay',
     'https://images.unsplash.com/photo-1525755662778-989d0524087e?w=800&auto=format&fit=crop&q=80',
     'Pechuga de pollo arrebozada y frita crocante, bañada en una suculenta salsa de ostión, canela china, sillao y cebollita china.'),
    ('Pollo Ti Pa Kay',
     'https://images.unsplash.com/photo-1625938145744-e380515399b7?w=800&auto=format&fit=crop&q=80',
     'Pechuga de pollo crocante en masa especial, servida con salsa tamarindo agridulce, piña en trozos y pimiento.'),
    ('Kam Lu Wantán',
     'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800&auto=format&fit=crop&q=80',
     'Wantanes fritos montados con pollo, chancho, langostinos, huevitos de codorniz, piña y verduras en salsa tamarindo.'),
    ('Chancho con Piña',
     'https://images.unsplash.com/photo-1544025162-d76694265947?w=800&auto=format&fit=crop&q=80',
     'Trozos de chancho asado crujiente salteados con piña fresca, pimientos y cebolla en salsa agridulce agripicante.'),
    ('Chicha Morada Clásica (1L)',
     'https://images.unsplash.com/photo-1556881286-fc6915169721?w=800&auto=format&fit=crop&q=80',
     'Refrescante chicha morada tradicional preparada con maíz morado, piña, manzana, canela, clavo de olor y toque de limón.'),
    ('Inca Kola 500ml',
     'https://images.unsplash.com/photo-1596343540266-130b3dbb1158?w=800&auto=format&fit=crop&q=80',
     'Gaseosa nacional de 500ml, bien helada. El maridaje dorado perfecto para tu chifa favorito.'),
    ('Coca Cola 500ml',
     'https://images.unsplash.com/photo-1554866585-cd94860890b7?w=800&auto=format&fit=crop&q=80',
     'Gaseosa Coca Cola clásica de 500ml, helada y refrescante.'),
    ('Té Jazmín Caliente',
     'https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=800&auto=format&fit=crop&q=80',
     'Té verde chino aromatizado con flores de jazmín natural, servido en tetera caliente. Digestivo y aromático.')
) AS v(name, image_url, description)
WHERE p.name = v.name;
"""


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("image_url", sa.String(length=500), nullable=True),
        schema="public",
    )
    op.add_column(
        "products",
        sa.Column("description", sa.String(length=500), nullable=True),
        schema="public",
    )
    op.execute(SEED_TABLES_SQL)
    op.execute(UPDATE_PRODUCT_IMAGES_SQL)


def downgrade() -> None:
    op.execute(
        "DELETE FROM public.restaurant_tables WHERE code IN "
        "('MESA-01','MESA-02','MESA-03','MESA-04','MESA-05','MESA-06','MESA-07','MESA-08','MESA-09','MESA-10');"
    )
    op.drop_column("products", "description", schema="public")
    op.drop_column("products", "image_url", schema="public")
