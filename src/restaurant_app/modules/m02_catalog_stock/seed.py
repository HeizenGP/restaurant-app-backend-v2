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
INSERT INTO public.products (id, category_id, name, price, stock_qty, is_available, image_url, description)
SELECT
    v.id,
    c.id,
    v.name,
    v.price,
    v.stock_qty,
    v.is_available,
    v.image_url,
    v.description
FROM (VALUES
    ('b0010001-0000-4000-a000-000000000001'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa Especial', 24.00, 50, TRUE,
     'https://images.unsplash.com/photo-1512058564366-18510be2db19?w=800&auto=format&fit=crop&q=80',
     'Clásico arroz chaufa al wok con pollo en trozos, lomo, chancho asado, langostinos, cebollita china y tortilla de huevo con toque secreto de sillao oscuro.'),
    ('b0010001-0000-4000-a000-000000000002'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Pollo', 18.00, 50, TRUE,
     'https://images.unsplash.com/photo-1603133872878-684f208fb84b?w=800&auto=format&fit=crop&q=80',
     'Arroz salteado al wok a fuego vivo con tiernos cubos de pollo, huevo, cebollita china fresca y aceite de ajonjolí tostado.'),
    ('b0010001-0000-4000-a000-000000000003'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Carne', 20.00, 50, TRUE,
     'https://images.unsplash.com/photo-1543339308-43e59d6b73a6?w=800&auto=format&fit=crop&q=80',
     'Sabroso chaufa tradicional salteado al wok con jugosos trozos de lomo de res, brotes de soya y cebolla china.'),
    ('b0010001-0000-4000-a000-000000000004'::uuid, 'Arroces y Chaufas', 'Aeropuerto Especial', 25.00, 40, TRUE,
     'https://images.unsplash.com/photo-1552611052-33e04de081de?w=800&auto=format&fit=crop&q=80',
     'Fusión contundente de arroz chaufa y fideo tallarín salteados al wok con pollo, carne, frejolito chino y huevo montado.'),
    ('b0010001-0000-4000-a000-000000000005'::uuid, 'Arroces y Chaufas', 'Arroz Chaufa de Chancho', 20.00, 40, TRUE,
     'https://images.unsplash.com/photo-1569058242253-92a9c755a0ec?w=800&auto=format&fit=crop&q=80',
     'Arroz chaufa con chancho laqueado dulce y aromático al estilo oriental con cebollita china crocante.'),
    ('b0010002-0000-4000-a000-000000000001'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Pollo', 19.00, 45, TRUE,
     'https://images.unsplash.com/photo-1585032226651-759b368d7246?w=800&auto=format&fit=crop&q=80',
     'Tallarines chinos salteados al wok con pechuga de pollo, pimiento rojo, holantao, col china y salsa de ostión.'),
    ('b0010002-0000-4000-a000-000000000002'::uuid, 'Tallarines y Saltados', 'Tallarín Saltado de Carne', 22.00, 45, TRUE,
     'https://images.unsplash.com/photo-1617093727343-374698b1b08d?w=800&auto=format&fit=crop&q=80',
     'Fideos gruesos salteados a fuego vivo con finas láminas de lomo de res, cebolla morada, tomate y salsa de soya.'),
    ('b0010002-0000-4000-a000-000000000003'::uuid, 'Tallarines y Saltados', 'Tallarín Taypa Especial', 26.00, 35, TRUE,
     'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?w=800&auto=format&fit=crop&q=80',
     'El rey de la casa: tallarines bañados en salsa especial con pollo, carne, chancho, langostinos, champiñones y verduras selectas.'),
    ('b0010002-0000-4000-a000-000000000004'::uuid, 'Tallarines y Saltados', 'Tallarín Sam Si', 24.00, 35, TRUE,
     'https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?w=800&auto=format&fit=crop&q=80',
     'Tallarines salteados con tiras de tres carnes seleccionadas: pollo, lomo y chancho con crujientes verduras orientales.'),
    ('b0010003-0000-4000-a000-000000000001'::uuid, 'Sopas y Entradas', 'Sopa Wantán Especial', 18.00, 30, TRUE,
     'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=800&auto=format&fit=crop&q=80',
     'Caldo dorado y reconfortante de ave con wantanes rellenos de cerdo y langostino, pollo en láminas, chancho asado y col china.'),
    ('b0010003-0000-4000-a000-000000000002'::uuid, 'Sopas y Entradas', 'Sopa Fuchifú', 16.00, 30, TRUE,
     'https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?w=800&auto=format&fit=crop&q=80',
     'Sopa espesada con clara de huevo hilada, trocitos de pechuga de pollo, champiñones y fideos de arroz en caldo aromático con kión.'),
    ('b0010003-0000-4000-a000-000000000003'::uuid, 'Sopas y Entradas', 'Wantán Frito con Salsa Tamarindo (12 un.)', 14.00, 60, TRUE,
     'https://images.unsplash.com/photo-1496116218417-1a781b1c416c?w=800&auto=format&fit=crop&q=80',
     'Docena de crocantes wantanes dorados rellenos de pasta de carne, acompañados de salsa de tamarindo agridulce artesanal.'),
    ('b0010003-0000-4000-a000-000000000004'::uuid, 'Sopas y Entradas', 'Siomay al Vapor (6 un.)', 16.00, 40, TRUE,
     'https://images.unsplash.com/photo-1541696432-82c6da8ce7bf?w=800&auto=format&fit=crop&q=80',
     'Bocaditos dim sum al vapor rellenos de carne de cerdo sazonada con kión, cebolla china y toque de ajonjolí.'),
    ('b0010004-0000-4000-a000-000000000001'::uuid, 'Especialidades', 'Pollo Chi Jau Kay', 23.00, 40, TRUE,
     'https://images.unsplash.com/photo-1525755662778-989d0524087e?w=800&auto=format&fit=crop&q=80',
     'Pechuga de pollo arrebozada y frita crocante, bañada en una suculenta salsa de ostión, canela china, sillao y cebollita china.'),
    ('b0010004-0000-4000-a000-000000000002'::uuid, 'Especialidades', 'Pollo Ti Pa Kay', 23.00, 40, TRUE,
     'https://images.unsplash.com/photo-1625938145744-e380515399b7?w=800&auto=format&fit=crop&q=80',
     'Pechuga de pollo crocante en masa especial, servida con salsa tamarindo agridulce, piña en trozos y pimiento.'),
    ('b0010004-0000-4000-a000-000000000003'::uuid, 'Especialidades', 'Kam Lu Wantán', 27.00, 35, TRUE,
     'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=800&auto=format&fit=crop&q=80',
     'Wantanes fritos montados con pollo, chancho, langostinos, huevitos de codorniz, piña y verduras en salsa tamarindo.'),
    ('b0010004-0000-4000-a000-000000000004'::uuid, 'Especialidades', 'Chancho con Piña', 24.00, 35, TRUE,
     'https://images.unsplash.com/photo-1544025162-d76694265947?w=800&auto=format&fit=crop&q=80',
     'Trozos de chancho asado crujiente salteados con piña fresca, pimientos y cebolla en salsa agridulce agripicante.'),
    ('b0010005-0000-4000-a000-000000000001'::uuid, 'Bebidas', 'Chicha Morada Clásica (1L)', 10.00, 100, TRUE,
     'https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=800&auto=format&fit=crop&q=80',
     'Refrescante chicha morada tradicional preparada con maíz morado, piña, manzana, canela, clavo de olor y toque de limón.'),
    ('b0010005-0000-4000-a000-000000000002'::uuid, 'Bebidas', 'Inca Kola 500ml', 4.50, 100, TRUE,
     'https://images.unsplash.com/photo-1622483767028-3f66f32aef97?w=800&auto=format&fit=crop&q=80',
     'Gaseosa nacional de 500ml, bien helada. El maridaje perfecto para tu chifa favorito.'),
    ('b0010005-0000-4000-a000-000000000003'::uuid, 'Bebidas', 'Coca Cola 500ml', 4.50, 100, TRUE,
     'https://images.unsplash.com/photo-1629203851122-3726ecdf080e?w=800&auto=format&fit=crop&q=80',
     'Gaseosa Coca Cola clásica de 500ml, helada y refrescante.'),
    ('b0010005-0000-4000-a000-000000000004'::uuid, 'Bebidas', 'Té Jazmín Caliente', 5.00, 80, TRUE,
     'https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=800&auto=format&fit=crop&q=80',
     'Té verde chino aromatizado con flores de jazmín natural, servido en tetera caliente. Digestivo y aromático.')
) AS v(id, category_name, name, price, stock_qty, is_available, image_url, description)
JOIN public.categories c ON c.name = v.category_name
ON CONFLICT (id) DO UPDATE SET
    image_url = EXCLUDED.image_url,
    description = EXCLUDED.description;
"""


async def seed_initial_catalog(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Safely seed initial categories and products if not already present."""
    async with session_factory() as session:
        async with session.begin():
            await session.execute(text(SEED_CATEGORIES_SQL))
            await session.execute(text(SEED_PRODUCTS_SQL))
        logger.info("Initial catalog categories and products ensured.")
