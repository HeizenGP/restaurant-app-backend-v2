# ETAPA 05 — Arquitectura de software

**Proyecto:** Restaurant App V2 — Chifa ASIA  
**Estado:** PROPUESTA DOCUMENTADA / PENDIENTE DE REVISIÓN Y APROBACIÓN  
**Fecha de elaboración:** 2026-10-14  
**Alcance:** arquitectura lógica de backend y Flutter, contratos de comunicación, seguridad, simulaciones y operación de agentes. No incluye código, dependencias instaladas, APIs ejecutables, tablas ni migraciones.

## 1. Fuentes y criterio de decisión

La línea base obligatoria son las ETAPAS 01–03 aprobadas: seis actores, roles acumulativos, tres modalidades, 40 RF, 11 RNF y RN confirmadas. La [ETAPA 04](etapa-04.md) y sus diagramas se usan como referencia de comportamiento **provisional**; esta propuesta no la aprueba ni resuelve sus pendientes.

Las decisiones de esta etapa se clasifican así:

- **Definida en ETAPA 05:** elección técnica propuesta, revisable hasta que el usuario apruebe esta etapa.
- **Heredada:** decisión de negocio aprobada en ETAPAS 01–03; la arquitectura no puede cambiarla.
- **Pendiente:** asunto que necesita ratificación y no puede convertirse en permiso, actor o funcionalidad por inferencia.

## 2. Decisiones principales

| ID | Decisión propuesta | Motivo |
|---|---|---|
| **A05-01** | Backend como **monolito modular FastAPI** con los siete módulos M01–M07. | Una sola operación académica, invariantes transversales y despliegue simple; no se justifican microservicios. |
| **A05-02** | Arquitectura hexagonal dentro de cada módulo y **Vertical Slicing por caso de uso**. | Aísla negocio y adaptadores, mantiene trazabilidad con RF/CA y permite pruebas por operación. |
| **A05-03** | Comunicación interna en proceso, síncrona para invariantes; eventos internos solo para efectos posteriores. **CQRS liviano**, sin event sourcing ni broker. | Evita infraestructura innecesaria y permite una única transacción para confirmar pedidos. |
| **A05-04** | Un workspace Flutter con dos aplicaciones: `customer_app` y `staff_app`; administración es un espacio adaptativo de `staff_app`. | Separa la experiencia pública de la operativa y conserva roles acumulativos sin mantener tres aplicaciones duplicadas. |
| **A05-05** | Una API REST JSON versionada bajo `/api/v1`; el backend es la autoridad de negocio. | Contrato único para ambos clientes y autorización centralizada. |
| **A05-06** | Sesiones de cliente, invitado y personal con tokens; autorización por permisos acumulados, comprobada en HTTP y en cada caso de uso. | Cumple RNF-01 y evita confiar en rutas o botones de Flutter. |
| **A05-07** | Servicios externos ausentes o simulados mediante adaptadores explícitos; sin llamadas reales a WhatsApp, pagos, mapas o SUNAT. | Respeta el alcance académico y evita fingir integraciones no aprobadas. |
| **A05-08** | Dos Skills locales y compartidas, carga documental selectiva y MCP por demanda. | Reduce redescubrimiento y contexto sin duplicar reglas en cada herramienta. |

Diagramas de apoyo:

- [ARQ-BE-01 — Componentes del backend](diagramas/etapa-05/etapa-05-backend-componentes.puml)
- [ARQ-FE-01 — Aplicaciones y paquetes Flutter](diagramas/etapa-05/etapa-05-frontend-componentes.puml)

## 3. Arquitectura del backend

### 3.1 Forma general

FastAPI es un adaptador de entrada. Pydantic, SQLAlchemy, PostgreSQL, JWT y cualquier simulador permanecen fuera del dominio. El arranque de la aplicación compone dependencias y monta routers; no contiene reglas de negocio.

Estructura objetivo para ETAPA 07, todavía **sin crear código**:

```text
src/restaurant_app/
├── bootstrap/                    # configuración, DI, middleware y composición de routers
├── shared/                       # primitivas técnicas realmente compartidas
│   ├── domain/                   # identificadores/valor monetario si dos o más módulos lo requieren
│   ├── application/              # clock, UoW, idempotencia, principal y errores base
│   └── infrastructure/           # configuración, observabilidad y adaptadores comunes
└── modules/
    └── mXX_nombre/
        ├── domain/               # entidades, objetos valor, políticas y eventos; Python puro
        ├── application/
        │   ├── ports/            # contratos requeridos por los casos de uso
        │   └── use_cases/
        │       └── verbo_objeto/ # command/query, handler y resultado del slice
        ├── adapters/
        │   ├── inbound/http/     # router, DTO y traducción HTTP
        │   └── outbound/         # persistencia o simuladores
        └── public.py             # contratos públicos mínimos del módulo
```

Reglas de dependencia:

1. `domain` no importa FastAPI, Pydantic, ORM, clientes HTTP ni otro módulo.
2. `application` depende del dominio y de puertos propios; cada handler implementa un caso de uso observable.
3. Los adaptadores dependen hacia adentro e intercambian DTO en el borde; un DTO HTTP no se convierte en entidad compartida.
4. Un módulo no importa el dominio, repositorio ni adaptador interno de otro. La composición conecta el puerto consumidor con la interfaz pública del proveedor.
5. `shared/` no aloja reglas de pedidos, stock, pagos o roles. Algo pasa a compartido solo si es estable y usado realmente por más de un módulo.
6. Los routers validan transporte y delegan. Las transiciones, permisos contextuales e invariantes viven en handlers/políticas.

### 3.2 Vertical Slicing y comunicación interna

Cada operación se localiza por intención, por ejemplo `m04_orders/application/use_cases/confirm_order/`, y contiene solo las piezas necesarias para esa operación. Se admite separar comandos y consultas para simplificar modelos de lectura, sin buses genéricos obligatorios ni duplicar el dominio.

La comunicación entre módulos sigue estas reglas:

- **Síncrona y en proceso** cuando una respuesta decide la misma operación: validar mesa, revalidar/descontar stock, comprobar anticipo, crear comanda o evaluar saldo.
- **Evento interno posterior al commit** para actualizar una proyección o auditoría que no determina el éxito de la transacción. No hay broker en esta versión.
- **Nunca HTTP entre módulos** del mismo proceso y nunca acceso directo a tablas ajenas.
- Los ciclos se evitan haciendo que el caso de uso consumidor defina el puerto requerido; `bootstrap` conecta su adaptador con la API pública del módulo proveedor.

`ConfirmOrder` de M04 es el coordinador del flujo crítico. Una única unidad de trabajo debe:

1. comprobar autorización y estado vigente del pedido;
2. revalidar disponibilidad y stock mediante M02;
3. comprobar en M06 el anticipo verificado cuando la modalidad lo exige;
4. aplicar una sola transición de confirmación y un solo descuento de stock;
5. habilitar una sola comanda mediante M05;
6. registrar actor, momento e identificador de la operación;
7. confirmar todos los cambios o ninguno.

El mecanismo concreto de concurrencia y persistencia se decide en ETAPA 06. La arquitectura exige atomicidad, control de versión y deduplicación para satisfacer RNF-04/05/10; no ratifica por sí sola RN-20 ni RN-21.

### 3.3 Límites de los siete módulos

| Módulo técnico | Responsabilidad y datos propios | Interfaz pública necesaria | Fuera de su límite | Trazas principales |
|---|---|---|---|---|
| **M01 `m01_access`** | Registro e inicio de sesión, sesión invitada, usuarios de personal, roles, permisos y principal autenticado. | Autenticar, renovar/revocar sesión, resolver permisos, administrar usuarios/roles. | No decide aprobación, caja ni reglas de modalidad. Invitado es tipo de sesión, no séptimo rol. | RF-M01-01..05; RN-02/03/04/13; RNF-01/02. |
| **M02 `m02_catalog_stock`** | Categorías, productos, precios vigentes, disponibilidad y cantidad de stock. | Consultar catálogo; gestionar catálogo; comprobar y descontar stock de forma atómica e idempotente. | No posee líneas, total ni estado del pedido; no confirma pedidos. | RF-M02-01..06; RN-09/10/11; RNF-04/09. |
| **M03 `m03_tables`** | Mesas, distribución y ocupación. | Consultar/gestionar mesas y validar una referencia de mesa. | La asociación seleccionada se guarda con el pedido en M04; M03 no aprueba solicitudes. | RF-M03-01..04; RN-01/06. |
| **M04 `m04_orders`** | Solicitud y snapshot comercial del pedido, modalidad, canal, líneas/cantidades/precios, total, decisiones y estado comercial (solicitado/aprobado/rechazado/confirmado/cerrado). | Crear/consultar, aprobar/rechazar y confirmar; componer la vista integrada del pedido mediante contratos públicos. | No copia como propios stock, pago, preparación o entrega ni accede a repositorios ajenos. | RF-M04-01..11; RN-05..10/12/14/15; RNF-04/09/10. |
| **M05 `m05_kitchen`** | Comanda vinculada a pedido confirmado y estado canónico de cocina: Recibida/En preparación/Listo. | Crear una sola comanda por confirmación; listar detalle/estado; cambiar estado autorizado. | No aprueba ni confirma pedidos, no registra cobros y no escribe directamente el estado comercial de M04. | RF-M05-01..04; RN-15/16. |
| **M06 `m06_payments`** | Cálculo de anticipo, verificación manual/simulada, cobros, deduplicación y saldo. | Verificar anticipo; registrar cobro; consultar estado/saldo. | No procesa dinero externo. Verificar anticipo no otorga permiso general de Caja. | RF-M06-01..06; RN-04/12/13/14/17/19; RNF-05/09. |
| **M07 `m07_fulfillment`** | Registro de servicio en mesa, recojo o entrega comercial y solicitud de cierre. | Registrar atención/entrega; evaluar cierre con estado de M04 y saldo de M06. | No administra repartidores, rutas o GPS. Actores de recojo/delivery/cierre siguen pendientes. | RF-M07-01..04; RN-17/18; RN-21 pendiente. |

Las referencias cruzadas no cambian la propiedad. Por ejemplo, M04 conserva el identificador de mesa y consulta M03; no duplica la mesa. M07 registra el hecho de atención y solicita la transición final a M04; la asignación de quién ejecuta recojo, delivery y cierre no se habilita hasta su ratificación.

El “estado del pedido” que ve el cliente es una **vista compuesta**, no un único campo compartido: M04 aporta el estado comercial; M05, el estado canónico de cocina; M06, pago/saldo; y M07, atención/entrega. El query de M04 consulta sus contratos públicos o una proyección derivada de eventos posteriores al commit. M05 no escribe el agregado de M04, y una proyección nunca reemplaza la fuente propietaria.

## 4. API REST y contratos

### 4.1 Convenciones

- Base `/api/v1`, JSON UTF-8 y fechas en ISO 8601 con zona horaria.
- `GET` no cambia estado; `POST` crea recursos o registra comandos de negocio; `PATCH` actualiza campos o una transición cuando el contrato lo haga inequívoco.
- Los comandos críticos aceptan `Idempotency-Key`: confirmar, verificar anticipo, registrar cobro, registrar atención/entrega y cerrar. Su alcance mínimo es principal + operación + recurso.
- Mutaciones concurrentes usan una versión esperada o precondición equivalente. Los conflictos de estado, stock o versión responden `409` con un código de dominio estable.
- Errores uniformes: `type`, `title`, `status`, `code`, `detail`, `instance`, `trace_id` y errores de campos cuando correspondan. No se exponen trazas internas.
- Códigos base: `400` solicitud mal formada, `401` sin sesión válida, `403` sin permiso, `404` recurso no visible, `409` conflicto de negocio/concurrencia, `422` datos semánticamente inválidos.
- Listados usan paginación y filtros explícitos. El contrato OpenAPI generado será fuente para clientes cuando exista en ETAPA 07; no se mantiene un segundo contrato manual divergente.
- REST es el único protocolo cliente-servidor de esta versión. Estados de pedido/comanda se actualizan mediante consulta o polling acotado; WebSocket, SSE y broker quedan fuera mientras no exista una necesidad aprobada.

### 4.2 Familias de rutas propuestas

Son fronteras de contrato, no APIs implementadas ni payloads definitivos.

| Módulo | Familias bajo `/api/v1` |
|---|---|
| M01 | `/auth/registrations`, `/auth/sessions`, `/auth/guest-sessions`, `/auth/refresh`, `/users`, `/roles` |
| M02 | `/catalog/categories`, `/catalog/products`, `/stock-adjustments` |
| M03 | `/tables`, `/table-occupancy` |
| M04 | `/orders`, `/orders/{id}/decisions`, `/orders/{id}/confirmations` |
| M05 | `/kitchen/commands`, `/kitchen/commands/{id}/transitions` |
| M06 | `/orders/{id}/advance-verifications`, `/orders/{id}/payments`, `/orders/{id}/payment-summary` |
| M07 | `/orders/{id}/fulfillments`, `/orders/{id}/closures` |

Las consultas de estado de un pedido permanecen en M04 aunque su vista combine proyecciones de cocina, pago y atención. No se crean endpoints externos para llamada o WhatsApp: el Administrador registra el canal al crear el pedido.

## 5. Autenticación y permisos

### 5.1 Sesiones

- **Cliente registrado:** token de acceso firmado y de corta duración más credencial de renovación rotativa.
- **Invitado:** sesión limitada emitida por el backend, con identificador propio y permisos de catálogo/mesa/pedido propio. No posee roles de personal.
- **Personal:** la misma forma de sesión, con uno o varios roles. Los permisos efectivos son la unión explícita de sus roles; Super Administrador obtiene el conjunto total.
- Contraseñas mediante un puerto de hash adaptativo; nunca se guardan o devuelven en claro. La biblioteca concreta se selecciona en ETAPA 07.
- Las credenciales de renovación se almacenarán revocables y protegidas; el detalle de persistencia pertenece a ETAPA 06.
- HTTPS es obligatorio para cualquier despliegue accesible por Internet. En móvil, Flutter guarda la credencial renovable en almacenamiento seguro y mantiene el acceso corto en memoria. Si se aprueba Flutter Web, la renovación usará cookie `HttpOnly`, `Secure` y `SameSite`, con origen permitido y protección CSRF; no `localStorage`.

### 5.2 Autorización

La interfaz puede ocultar destinos por capacidad, pero cada handler vuelve a comprobar permiso, propiedad del recurso, modalidad, canal y estado. Los roles no se comparan directamente dentro del dominio cuando una capacidad expresa mejor la intención.

| Capacidad | Cliente/invitado | Mozo | Cajero | Administrador | Cocina | Super Admin |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Consultar catálogo / mesas aplicables | ✓ | ✓ | — | ✓ | — | ✓ |
| Crear y consultar pedido propio | ✓ | — | — | — | — | ✓ |
| Gestionar usuarios de personal y roles | — | — | — | ✓ | — | ✓ |
| Registrar pedido local presencial | — | ✓ | — | — | — | ✓ |
| Aprobar app local / confirmar local | — | ✓ | — | ✓ | — | ✓ |
| Registrar canal externo / aprobar recojo-delivery | — | — | — | ✓ | — | ✓ |
| Gestionar catálogo, stock y registro/distribución de mesas | — | — | — | ✓ | — | ✓ |
| Consultar/actualizar ocupación de mesas | — | ✓ | — | ✓ | — | ✓ |
| Consultar/actualizar comanda | — | — | — | — | ✓ | ✓ |
| Registrar cobros generales | — | — | ✓ | Solo con rol Cajero adicional | — | ✓ |
| Verificar anticipo | — | — | — | ✓ | — | ✓ |
| Registrar servicio en mesa | — | ✓ | — | — | — | ✓ |
| Registrar recojo/delivery/cierre | — | — | — | **Pendiente** | — | ✓ |

El último permiso no se concede al Administrador por esta tabla: se conserva como pendiente de la ETAPA 04. El acceso total de Super Administrador sí es una regla aprobada.

## 6. Estrategia de simulación y servicios externos

| Caso | Decisión de ETAPA 05 | Evidencia/seguridad |
|---|---|---|
| Llamada y WhatsApp | Son valores de canal y entrada manual por Administrador; no existe cliente HTTP ni webhook. | Guardar canal y actor que registró. |
| Anticipo/pago | Adaptador `manual_simulated`: el Administrador verifica anticipo y Caja registra cobros. No se captura dinero ni se consulta un banco. | Marcar origen manual/simulado, actor, fecha e idempotency key. |
| Cancelación con anticipo | El Administrador decide manualmente si corresponde devolverlo, fuera de un flujo automatizado. | RN-19 no crea endpoint, puerto de reembolso ni movimiento de dinero; añadirlos exigiría un RF autorizado. |
| Delivery | Registro comercial manual de entrega. | Sin repartidor, asignación, ruta, mapa o GPS. |
| Facturación/SUNAT | Sin puerto, adaptador, endpoint ni pantalla. | No existe RF aprobado; cualquier incorporación exige volver a requisitos. |
| Pruebas | Fakes deterministas de reloj, IDs, repositorios y puertos externos. | Sin red ni secretos; resultados repetibles y rotulados como simulados. |

Los adaptadores se seleccionan por composición/configuración y nunca por condicionales dentro del dominio. Una futura integración real debe implementar el mismo puerto, tener autorización explícita y abrir su propia decisión arquitectónica.

## 7. Arquitectura Flutter

### 7.1 Organización de aplicaciones

| Alternativa | Evaluación |
|---|---|
| Una app para todos | Menos artefactos, pero mezcla acceso público y operación interna, aumenta rutas sensibles y complica la experiencia. |
| **Dos apps: cliente + personal/administración** | **Elegida.** Separa contextos de uso y permite que una cuenta con varios roles opere en una sola sesión de personal. |
| Tres apps: cliente + personal + administración | Aísla administración, pero duplica sesión, API, diseño y módulos; fragmenta a Administrador + Cajero sin una necesidad actual. |

- `customer_app`: Android móvil para Cliente registrado o Invitado; consume M01–M04 y consulta el estado integrado del pedido.
- `staff_app`: Android/adaptativa para Mozo, Cajero, Cocina, Administrador y Super Administrador; habilita espacios según capacidades. Las vistas administrativas se adaptan a tablet/web/escritorio desde el mismo código. El destino de despliegue inicial del panel se confirma en ETAPA 07.

Estructura objetivo, aún sin inicializar Flutter:

```text
apps/
├── customer_app/lib/
│   ├── app/                      # arranque, navegación y tema
│   └── features/mXX_nombre/
│       ├── shared/domain/        # modelo estable del módulo, si se reutiliza
│       └── verbo_objeto/         # slice usado por cliente
└── staff_app/lib/
    ├── app/                      # shell por capacidades y navegación
    └── features/mXX_nombre/
        ├── shared/domain/
        └── verbo_objeto/         # slice operativo M01–M07
packages/
├── foundation/                  # Result, errores, reloj e instrumentación mínimos
├── rest_api/                    # transporte, DTO REST y traducción de errores
├── auth_session/                # sesión/token y capacidades efectivas
└── design_system/               # tokens y componentes visuales compartidos
```

Cada slice contiene solo las capas que necesita y mantiene dependencias hacia adentro:

```text
presentation → application → domain
infrastructure ────────────────┘
```

`presentation` contiene páginas, componentes y controladores de estado; `application`, el caso de uso y sus puertos; `domain`, modelos/reglas Dart puras que el slice comparte dentro de su módulo; `infrastructure`, repositorios REST y mapeadores. Los DTO viven en `rest_api`, no se muestran directamente en widgets. No se extrae un paquete de negocio compartido hasta demostrar reutilización real entre las dos apps.

### 7.2 Estado, navegación y datos

- Flujo de estado unidireccional e inmutable por pantalla/caso de uso: `idle/loading/success/empty/failure` más estados de comando cuando apliquen.
- Navegación declarativa con guardas por sesión y capacidad. Escribir una URL o conservar una ruta no concede permiso.
- El servidor es fuente de verdad para stock, aprobación, pago y estado. Puede existir caché de lectura; una mutación solo muestra éxito tras confirmación del servidor (RNF-10).
- Los reintentos de comandos reutilizan su `Idempotency-Key`; la UI evita dobles envíos pero no sustituye la deduplicación del backend.
- `rest_api` renueva sesión una sola vez ante expiración y traduce el error uniforme a fallos tipados. Un `403` no se reintenta como si fuera desconexión.
- Las decisiones de paquetes concretos para estado, navegación, DI y cliente HTTP se toman en ETAPA 07 tras comprobar compatibilidad; estas fronteras no dependen de una librería.

## 8. Skills, agentes y MCP

Se preparan dos Skills canónicas, compatibles con Codex y AGY mediante `.agents/skills/`. Cada una vive solo en el repositorio donde se aplica; no existen copias por herramienta:

| Skill | Usar cuando | No cargar cuando |
|---|---|---|
| `restaurant-fastapi-slice` en `restaurant-app-backend-v2/.agents/skills/` | Diseñar, implementar o revisar un caso de uso del backend M01–M07. | Tareas solo Flutter o edición documental general. |
| `restaurant-flutter-slice` en `restaurant-app-frontend-v2/.agents/skills/` | Diseñar, implementar o revisar una feature de `customer_app` o `staff_app`. | Tareas solo backend o requisitos. |

Codex y AGY consumen el mismo archivo de cada repositorio; no se mantienen copias por herramienta ni metadata específica de una interfaz. `AGENTS.md` contiene únicamente reglas siempre activas y rutas de carga. Esta guía y las Skills enlazan la arquitectura en vez de copiarla.

Carga mínima recomendada:

1. Siempre: `AGENTS.md`, `docs/etapas/README.md` y el documento de la etapa vigente.
2. Tarea técnica: una sola Skill pertinente y las secciones/RF concretos que afecte.
3. Flujo transversal: únicamente los diagramas de ETAPA 04 relacionados; recordar su estado provisional.
4. Leer ETAPAS 01–02 solo si una duda de negocio no queda resuelta por RF/RN.
5. Leer los archivos compartidos en un repositorio y comprobar igualdad en el otro; no cargar ambas copias al contexto.

MCP se usa por necesidad demostrada: archivos y Git locales para este trabajo; GitHub solo para operaciones remotas solicitadas; Figma en ETAPA 09; conectores externos únicamente si una etapa los autoriza. No se conecta una herramienta para volver a leer contenido local ya disponible.

## 9. Trazabilidad de RNF y validación

| RNF | Respuesta arquitectónica |
|---|---|
| RNF-01 | Principal y permisos en adaptador HTTP y handler; matriz de capacidades. |
| RNF-02 | Puerto de hash adaptativo y credenciales nunca expuestas. |
| RNF-03 | HTTPS obligatorio en despliegue público. |
| RNF-04 | UoW de confirmación, control de concurrencia e idempotencia. |
| RNF-05 | Registro de cobro idempotente y saldo propiedad de M06. |
| RNF-06 | Contrato uniforme de error y traducción tipada en Flutter. |
| RNF-07 | `customer_app` Android móvil y `staff_app` adaptativa. |
| RNF-08 | La métrica p95 <= 3 s / 20 usuarios permanece propuesta; no se usa como aprobación. |
| RNF-09 | Auditoría de actor, instante e identificador para aprobación, stock, anticipo y cobro. |
| RNF-10 | Éxito solo tras respuesta del servidor y reintentos con la misma clave. |
| RNF-11 | Módulos aislables, puertos sustituibles y pruebas por slice/integración. |

Criterios de validación de esta propuesta:

- [x] Los 40 RF conservan un módulo propietario M01–M07.
- [x] Roles acumulativos, Super Administrador, límites de Cajero y verificación de anticipo están reflejados.
- [x] Confirmación, stock, comanda y pagos tienen fronteras y consistencia explícitas.
- [x] Las dos apps Flutter cubren cliente, personal y administración sin crear actores.
- [x] Simulaciones/exclusiones no se presentan como integraciones reales.
- [x] Las Skills enlazan una fuente arquitectónica única y evitan repetir reglas.
- [ ] Renderizar los diagramas de ETAPA 05 cuando PlantUML esté disponible.
- [ ] Aprobar expresamente ETAPA 04 y luego revisar cualquier impacto sobre esta arquitectura.
- [ ] Aprobar expresamente ETAPA 05; este documento no la autoaprueba.

## 10. Pendientes conservados

1. Aprobación y correcciones de la ETAPA 04.
2. Responsable de registrar recojo, entrega delivery y cierre en M07; no se asigna al Administrador por defecto.
3. Estado formal de RN-20 y RN-21. Sus resultados coinciden parcialmente con RF/RNF aprobados, pero esta etapa no cambia su etiqueta pendiente.
4. Ratificar o reemplazar la métrica propuesta RNF-08.
5. Ratificar exclusiones aún propuestas, incluida facturación electrónica; hasta entonces permanecen fuera de implementación.
6. En ETAPA 06: modelo de datos, límites transaccionales físicos, bloqueo/control de versión e idempotencia persistida.
7. En ETAPA 07: versiones y librerías concretas, algoritmo/configuración de tokens, framework de estado/navegación/DI y primer destino del panel adaptativo.

**Estado final: ETAPA 05 DOCUMENTADA Y PENDIENTE DE APROBACIÓN.** No instalar ni implementar esta arquitectura hasta que la etapa correspondiente lo autorice.
