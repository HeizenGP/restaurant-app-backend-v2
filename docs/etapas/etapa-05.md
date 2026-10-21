# ETAPA 05 — Arquitectura de software | Chifa ASIA

**Estado:** DOCUMENTADA / PENDIENTE DE APROBACIÓN  
**Revisión:** 2026-10-20 · **Rama:** `develop`  
**Base:** ETAPAS 01–04 aprobadas (40 RF, 11 RNF, 7 módulos y 6 actores). Esta etapa define la arquitectura; **no implementa código ni base de datos**.

## 1. Vista general

```text
Flutter (Dart)
├── customer_app  → Clientes (Android)
└── staff_app     → Mozo, cocina y caja (Android)
                    Administración (Flutter Web)
           │
           ▼ REST / JSON
Backend Python + FastAPI
    Arquitectura hexagonal + Vertical Slicing
    Monolito modular M01–M07
           │
           ▼ SQLAlchemy Async + asyncpg
     PostgreSQL
```

**Decisión:** dos aplicaciones Flutter y una API FastAPI. El panel administrativo es **Flutter Web dentro de `staff_app`**; no existe una tercera app ni microservicios.

## 2. Tecnologías definidas

| Capa | Tecnología | Función |
|---|---|---|
| Backend | **Python + FastAPI** | API REST |
| Validación | **Pydantic** | Datos de entrada y salida |
| ORM | **SQLAlchemy Async** | Persistencia asíncrona |
| Driver PostgreSQL | **asyncpg** | Conexión asíncrona |
| Migraciones | **Alembic** | Evolución del esquema |
| Base de datos | **PostgreSQL** | Datos del restaurante |
| Autenticación | **JWT + Argon2** | Sesiones y contraseñas |
| Entorno local | **Docker** | PostgreSQL en desarrollo |
| Frontend | **Flutter + Dart** | Aplicaciones y panel web |
| Diseño UI/UX | **Figma + iconos Lucide** | Diseños de la ETAPA 09 |
| Versionado | **Git + GitHub** | Repositorios backend/frontend |

Las versiones y bibliotecas concretas de soporte se fijarán al configurar los proyectos en ETAPA 07. Estas tecnologías son el **stack previsto**, no una afirmación de que ya estén instaladas.

## 3. Backend

**Estilo:** monolito modular, arquitectura **hexagonal** en cada módulo y **Vertical Slicing** por caso de uso.

**Estructura objetivo (sin carpeta de inicialización independiente):**

```text
src/restaurant_app/
├── main.py                   # Crea FastAPI y registra rutas
├── core/
│   ├── config.py             # Configuración
│   └── dependencies.py       # Conecta casos de uso y adaptadores
├── modules/
│   ├── m01_access/
│   ├── m02_catalog_stock/
│   ├── m03_tables/
│   ├── m04_orders/
│   ├── m05_kitchen/
│   ├── m06_payments/
│   └── m07_fulfillment/
└── shared/                   # Solo utilidades realmente comunes
```

**Dentro de cada módulo** (ejemplo `m04_orders/`):

```text
m04_orders/
├── domain/                   # Reglas de negocio, Python puro
├── application/
│   ├── ports/                # Contratos necesarios
│   └── use_cases/            # Slices: confirm_order/, etc.
├── adapters/
│   ├── inbound/http/         # Endpoints FastAPI
│   └── outbound/             # Repositorios SQLAlchemy
└── public.py                 # Contratos públicos del módulo
```

- `main.py` inicia la API; `core/dependencies.py` ensambla dependencias y las unidades de trabajo. **No hay carpeta ni framework adicional de arranque.**
- `domain/` no importa FastAPI, Pydantic o SQLAlchemy. Cada módulo posee sus puertos y adaptadores; se comunica con otros a través de contratos públicos, no mediante sus tablas o repositorios internos.
- Los módulos se organizan por funcionalidades, no por carpetas globales de `models/`, `routers/` y `services/`.

### Módulos del negocio

| Módulo | Responsabilidad |
|---|---|
| M01 Accesos | Usuarios, sesiones, roles y permisos |
| M02 Catálogo y stock | Productos, precios, disponibilidad y existencias |
| M03 Mesas | Mesas y ocupación |
| M04 Pedidos | Solicitudes, aprobación y confirmación |
| M05 Cocina | Comandas y preparación |
| M06 Caja y pagos | Anticipos simulados, cobros y saldo |
| M07 Atención y cierre | Servicio, entrega comercial y cierre |

### Tres reglas técnicas críticas

**Confirmación del pedido:** M04 coordina **una sola transacción** de PostgreSQL mediante una unidad de trabajo compartida: valida permisos/estado, verifica stock (M02), consulta anticipo cuando corresponda (M06), confirma, descuenta stock **una vez** y crea **una comanda** (M05). Todo se confirma junto o se revierte; reintentos no duplican operaciones. El bloqueo y mecanismo físico se definen en ETAPA 06.

**Anticipo del 50 %:** en recojo y delivery, M06 registra **un único abono simulado** al verificarlo el Administrador. Ese importe reduce el saldo; confirmar el pedido no registra un segundo pago. El permiso del Administrador para verificar anticipos **no lo habilita como Cajero**. Los cobros posteriores corresponden a Caja.

**Seguridad:** sesión de Cliente/Invitado o Personal con JWT, contraseñas con Argon2 y autorización en cada caso de uso. Los roles son acumulativos y Superadministrador tiene acceso total; el frontend nunca sustituye los permisos del backend.

### Comunicación

API REST `/api/v1` con JSON. Los comandos críticos usan `Idempotency-Key` y errores uniformes (401, 403, 404, 409, 422). OpenAPI se generará desde FastAPI cuando se implemente.

**Recursos orientativos:** `/orders`, `/catalog/products`, `/tables`, `/kitchen/tickets`, `/orders/{id}/payments`. Son ejemplos de familias de rutas, no endpoints ya creados.

## 4. Frontend

**Tecnología:** Flutter + Dart. Ambas aplicaciones consumen la **misma API**; el backend es la fuente de verdad.

| Aplicación | Usuarios / destino |
|---|---|
| `customer_app` | Cliente registrado o invitado · **Android** |
| `staff_app` | Mozo, cocina, cajero · **Android**; Administrador y Superadministrador · **Flutter Web** (panel del mismo proyecto) |

**Estructura objetivo:**

```text
apps/
├── customer_app/
│   └── lib/
│       ├── app/                  # Tema y navegación
│       └── features/             # Slices M01–M04
└── staff_app/
    └── lib/
        ├── app/                  # Sesión y navegación por permisos
        └── features/             # Slices M01–M07
packages/
├── foundation/                   # Tipos/utilidades comunes
├── rest_api/                     # Cliente HTTP y DTO
├── auth_session/                 # Sesión y capacidades
└── design_system/                # Tema y componentes compartidos
```

Cada slice separa presentación, caso de uso y adaptador REST cuando sean necesarios. **No se duplican reglas del backend en Flutter**. El panel Web utiliza el mismo `staff_app`; se publica con configuración propia en ETAPA 07.

**UI:** tema claro predominante, modo oscuro opcional, diseño definido en Figma y iconos Lucide. La elección de librerías de estado y navegación se realizará en ETAPA 07, evitando dependencias anticipadas.

## 5. Límites y herramientas de desarrollo

- Pagos, anticipos y comprobantes: **simulados**. Sin pasarela real ni integración SUNAT.
- WhatsApp/llamadas: **registro manual**, sin integración externa.
- Delivery: **registro comercial**, sin GPS, rutas o logística de repartidores.
- Dos Skills: `restaurant-fastapi-slice` (backend) y `restaurant-flutter-slice` (frontend). Ambos agentes usan `AGENTS.md`; la documentación compartida está en `docs/`.
- Los RF/criterios de aceptación siguen siendo la referencia oficial en [ETAPA 03](etapa-03.md); los casos de uso aprobados están en [ETAPA 04](etapa-04.md). **No se alteran aquí.**

## 6. Validación y pendientes

- [x] Dos aplicaciones Flutter y una API FastAPI.
- [x] Monolito modular con Hexagonal + Vertical Slicing, sin carpeta de arranque adicional.
- [x] Stack técnico, módulos y estructura objetivo documentados.
- [x] Confirmación atómica, anticipo simulado y separación de permisos descritos.
- [x] La arquitectura y estructura de backend/frontend están descritas en este archivo, sin diagramas adicionales.
- [ ] Validar automáticamente las Skills.
- [ ] **Aprobación expresa del usuario de la ETAPA 05.**

**Pendientes que no se deciden en esta etapa:** responsables de recojo/delivery/cierre de M07, estado formal de RN-20/RN-21, métrica RNF-08 y exclusiones aún propuestas. ETAPA 06 definirá modelo de datos, concurrencia e idempotencia persistida. ETAPA 07 concretará versiones, librerías y despliegue.

**Estado final: ETAPA 05 DOCUMENTADA / PENDIENTE DE APROBACIÓN.**
