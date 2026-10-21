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

## 6. Hoja de ruta de desarrollo de los módulos (M01–M07)

**Alcance:** plan de implementación, no código. La fuente obligatoria es [ETAPA 03: 40 RF y criterios de aceptación](etapa-03-requisitos.md), validada con el [flujo de ETAPA 02](etapa-02.md) y los [8 casos de uso aprobados en ETAPA 04](etapa-04.md). Cada RF conserva su identificador y módulo propietario.

### 6.1 Orden técnico recomendado

| Orden | Módulo y RF | Backend FastAPI | Interfaz Flutter y comprobación de salida |
|---|---|---|---|
| **1** | **M01 · Usuarios y accesos** · RF-M01-01 a 05 | Registro/login, acceso invitado, sesiones, roles múltiples y autorización. | `customer_app`: registro, ingreso, invitado. `staff_app`: acceso por permisos. **Comprobar** bloqueo de acciones no autorizadas y acceso total del Superadministrador. |
| **2** | **M02 · Catálogo y stock** · RF-M02-01 a 06 | Categorías, productos, precios, disponibilidad, stock y contratos para validar/descontar una sola vez al confirmar. | Catálogo del cliente y gestión administrativa. **Comprobar** producto deshabilitado, stock insuficiente y ausencia de descuento en solicitudes pendientes. |
| **3** | **M03 · Mesas** · RF-M03-01 a 04 | Registro/distribución, ocupación, consulta y asociación de mesa al pedido local. | Selección de mesa en `customer_app` y vista para Mozo/Administrador en `staff_app`. **Comprobar** autorización y mesa asociada. |
| **4** | **M06-A · Anticipo** · RF-M06-02 a 04 | Cálculo del 50 %, verificación por Administrador y un único abono simulado por operación válida. | Verificación administrativa en `staff_app`. **Comprobar** bloqueo sin anticipo en recojo/delivery y ausencia de duplicación; sin conceder rol Cajero. |
| **5** | **M04 · Pedidos** · RF-M04-01 a 11 | Registro por modalidad/canal, total, revisión por rol, rechazo y `ConfirmOrder` con una transacción que valida M02/M06 y habilita M05. | Creación/seguimiento en `customer_app`; registro y aprobación en `staff_app`. **Comprobar** pedido presencial sin segunda aprobación, verificación presencial de mesa en app local y aprobación administrativa en recojo/delivery. |
| **6** | **M05 · Cocina y comandas** · RF-M05-01 a 04 | Una comanda por pedido confirmado, detalle/cantidades y estados En preparación/Listo. Integración transaccional con M04. | Vista de cocina en `staff_app`. **Comprobar** que una solicitud pendiente/rechazada no aparece y que Listo exige preparación completa. |
| **7** | **M06-B · Caja y pagos** · RF-M06-01, 05 y 06 | Registro de cobros por Cajero, saldo y cobro del 50 % restante al entregar recojo/delivery. Reutiliza M06-A, sin doble contabilización. | Caja en `staff_app`. **Comprobar** pagos registrados, saldo correcto y bloqueo de cierre con deuda. |
| **8** | **M07 · Atención, entregas y cierre** · RF-M07-01 a 04 | Registro de servicio en mesa, recojo o delivery; verificación de atención/entrega y saldo antes del cierre. | Mozo registra servicio local; otras acciones se habilitarán **solo tras ratificar responsables**. **Comprobar** bloqueo de cierre sin entrega o con saldo pendiente. |

**Nota:** M06-A y M06-B son **dos incrementos del mismo módulo M06**, no dos módulos nuevos. M04 se completa integrando los contratos de M02, M06 y M05; no se duplica su lógica. Las interfaces se implementan en ETAPA 10, una vez definidos sus diseños en ETAPA 09.

### 6.2 Cuándo se ejecuta la hoja de ruta

| Etapa oficial | Trabajo previsto |
|---|---|
| **06 · Base de datos** | Modelar PostgreSQL para los siete módulos, integridad de pedidos/stock/cobros y soporte físico de transacciones e idempotencia. **Solo diseño.** |
| **07 · Configuración técnica** | Inicializar FastAPI, SQLAlchemy Async, Alembic, PostgreSQL/Docker y el workspace Flutter; preparar entornos y migraciones iniciales autorizadas. |
| **08 · Backend** | Implementar **en el orden 1–8 anterior** los casos de uso, API y pruebas de los 40 RF. Validar transacción única M04–M02–M05 y anticipo M06 antes de integrar todo. |
| **09 · Diseño UX/UI** | Diseñar en Figma pantallas de `customer_app`, `staff_app` y panel Flutter Web según RF/CU. Puede avanzar en paralelo a ETAPA 08 con contratos estables. |
| **10 · Frontend** | Implementar slices Flutter por módulos, según las capacidades de cada rol, conectados a la API validada; no crear una tercera app. |
| **11 · Integración y entrega** | Probar los tres recorridos (local, recojo y delivery), autorizaciones, rechazo, stock, anticipo, cocina, cobro y cierre frente a los CA aprobados. |

**Criterio de finalización de cada módulo:** sus RF y CA pertinentes están implementados, las restricciones de rol se prueban en backend, los errores son manejados y los flujos funcionan con los módulos de los que depende. No afirmar funcionalidades ni pruebas ejecutadas durante la presente ETAPA 05.

### 6.3 Decisiones pendientes que no deben inventarse

- **M07:** responsable de registrar recojo, entrega delivery y cierre; antes de desarrollar esas acciones, ratificar permisos.
- **RN-20 y RN-21:** mantener su estado formal pendiente, sin presentarlas como reglas ratificadas por esta hoja de ruta.
- **RNF-08:** métrica de rendimiento aún propuesta.
- **Alcance:** sin sedes, inventario de ingredientes, repartidores/GPS, integración con WhatsApp, pasarelas ni SUNAT. Las exclusiones aún propuestas no se convierten en aprobaciones.

## 7. Validación y pendientes

- [x] Dos aplicaciones Flutter y una API FastAPI.
- [x] Monolito modular con Hexagonal + Vertical Slicing, sin carpeta de arranque adicional.
- [x] Stack técnico, módulos y estructura objetivo documentados.
- [x] Confirmación atómica, anticipo simulado y separación de permisos descritos.
- [x] Hoja de ruta M01–M07 trazada a los 40 RF de ETAPA 03 y a las ETAPAS 06–11.
- [x] La ETAPA 05 no conserva diagramas de arquitectura: la estructura y la secuencia de desarrollo se documentan en este archivo.
- [ ] Validar automáticamente las Skills.
- [ ] **Aprobación expresa del usuario de la ETAPA 05.**

**Pendientes que no se deciden en esta etapa:** responsables de recojo/delivery/cierre de M07, estado formal de RN-20/RN-21, métrica RNF-08 y exclusiones aún propuestas. ETAPA 06 definirá modelo de datos, concurrencia e idempotencia persistida. ETAPA 07 concretará versiones, librerías y despliegue.

**Estado final: ETAPA 05 DOCUMENTADA / PENDIENTE DE APROBACIÓN.**
