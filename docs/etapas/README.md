# Plan maestro de desarrollo — Restaurant App V2

**Proyecto:** Chifa ASIA — sistema académico para un solo restaurante.  
**Actualización:** 2026-10-21. **Rama de trabajo:** develop.

**Estado:** ETAPAS 00–06 **aprobadas expresamente por el usuario** (ETAPAS 04–05: aprobación documental el 2026-10-20; ETAPA 06: aprobación documental el 2026-10-21); ETAPA 07 **implementada y pendiente de revisión/aprobación**; ETAPAS 08–11 **por desarrollar**. La ETAPA 05 incluye dos Skills configuradas y verificadas estructuralmente (sin prueba de ejecución en IDE). No confundir implementación verificada con aprobación del usuario.

## 1. Propósito y reglas del plan

Desarrollar progresivamente un ecosistema para clientes, mozos, caja, cocina y administración, conservando las decisiones aprobadas de negocio. Este archivo es la **hoja de ruta ejecutiva**: el detalle y la evidencia pertenecen al documento de cada etapa, no se duplican aquí.

**Línea base:** seis actores (Cliente, Mozo, Cajero, Administrador, Personal de cocina y Super Administrador), roles acumulativos, modalidades **consumo en local, recojo y delivery**, siete módulos **M01–M07**, **40 RF** y **11 RNF** documentados en ETAPA 03.

**Reglas transversales que no deben cambiarse por una decisión técnica:**

- **Local por mozo:** registra y confirma sin segunda aprobación; **local por app:** Mozo o Administrador comprueba presencialmente la mesa antes de aprobar.
- **Recojo/delivery por app:** aprobación del Administrador; **por llamada/WhatsApp:** registro y validación manual del Administrador.
- **Recojo/delivery:** anticipo verificado del **50 % antes de cocina**; el saldo restante se registra al entregar.
- **Stock:** comprobar antes de confirmar y descontar una sola vez al confirmar; las solicitudes pendientes no descuentan existencias.
- **Cocina y cierre:** solo pedidos confirmados generan comandas; cocina registra preparación/listo, y la atención/cobro se registran según modalidad.
- **Alcance académico:** pago/anticipo manual o simulado, sin pasarela bancaria; llamada/WhatsApp sin integración automática; delivery sin repartidores, rutas ni GPS. La facturación SUNAT no se incorpora sin RF y aprobación explícitos. No asumir nuevas funciones por analogía con versiones antiguas.
- **Pendientes explícitos:** RN-20/RN-21, métrica RNF-08, responsables de operaciones M07 y exclusiones propuestas se conservan identificados hasta una decisión expresa.

## 2. Estado y secuencia

| Etapa | Nombre | Estado | Fuente/entregable principal |
|---|---|---|---|
| **00** | Configuración de agentes de IA | **Aprobada** | [Configuración y reglas](etapa-00.md) |
| **01** | Análisis del negocio y alcance | **Aprobada** | [Análisis del negocio](etapa-01.md) |
| **02** | Flujo principal y subflujos | **Aprobada** | [Flujos](etapa-02.md) y [FL-01](etapa-02-flujo-principal.puml) |
| **03** | Ingeniería de requisitos | **Aprobada** | [Reglas/RNF](etapa-03.md) y [40 RF/CA](etapa-03-requisitos.md) |
| **04** | Modelado del sistema | **Aprobada por el usuario (2026-10-20), con verificaciones técnicas pendientes** | [Casos de uso UML](etapa-04.md) y [8 diagramas CU](diagramas/etapa-04/) |
| **05** | Arquitectura de software | **Aprobada (2026-10-20)** | [Arquitectura y tecnologías](etapa-05.md) y Skills técnicas |
| **06** | Diseño de base de datos | **Aprobada (2026-10-21)** | [Modelo PostgreSQL y trazabilidad](etapa-06.md), [DER editable](diagramas/etapa-06/etapa-06-der.drawio) |
| **07** | Configuración técnica | **Implementada; pendiente de revisión/aprobación** | [Implementación y evidencia](etapa-07.md), infraestructura y migraciones iniciales |
| **08** | Desarrollo del backend | Por iniciar | API REST y pruebas de los siete módulos |
| **09** | Diseño UX/UI en Figma | Por iniciar | Interfaces y prototipos aprobados |
| **10** | Desarrollo del frontend | Por iniciar | Apps Flutter conectadas al backend |
| **11** | Integración, pruebas y entrega | Por iniciar | Validación extremo a extremo y demostración académica |

La elaboración de una etapa no equivale a su aprobación, ni una casilla de documentación a una prueba técnica ejecutada. **No iniciar trabajo dependiente de decisiones pendientes sin resolver su impacto primero.**

## 3. Etapas y criterios de cierre

### ETAPA 00 — Configuración de agentes de IA · APROBADA

**Objetivo:** coordinar Codex y AGY con reglas mínimas y contexto selectivo.

- Definir ahorro de tokens, reglas compartidas en **AGENTS.md**, organización de **docs/** y uso de MCP por necesidad.
- Separar instrucciones permanentes de documentación extensa; no instalar frameworks ni implementar funciones en esta etapa.
- Reservar Skills de FastAPI y Flutter para su definición arquitectónica en ETAPA 05.

**Entregable/cierre:** instrucciones y flujo de trabajo de agentes documentados y validados en ambos repositorios. [Evidencia](etapa-00.md).

### ETAPA 01 — Análisis del negocio y alcance · APROBADA

**Objetivo:** definir qué hará Chifa ASIA, quién operará cada función y qué se simulará.

- Describir problema, objetivos, actores/permisos acumulativos, modalidades/canales y responsabilidades.
- Delimitar los **7 módulos**: M01 Accesos, M02 Catálogo/stock, M03 Mesas, M04 Pedidos, M05 Cocina, M06 Caja/pagos, M07 Atención/entregas.
- Clasificar capacidades incluidas, manuales/simuladas, excluidas y expresamente pendientes; no diseñar APIs ni base de datos.

**Entregable/cierre:** [alcance y reglas de negocio](etapa-01.md), trazables y sin decisiones implícitas.

### ETAPA 02 — Flujo principal y subflujos del negocio · APROBADA

**Objetivo:** representar el pedido desde que el cliente lo solicita hasta atención, cobro y cierre.

- Mantener un **FL-01 principal** con modalidad/canal: local (mozo/app), recojo (app/llamada/WhatsApp), delivery (app/llamada/WhatsApp).
- Representar aprobaciones, mesa presencial, validación/descuento de stock, anticipo, comanda, preparación, entrega y cobro.
- Documentar excepciones esenciales: rechazo, falta de stock, anticipo no confirmado y cancelación con anticipo; no modelar logística de repartidores.

**Entregable/cierre:** [flujo documentado](etapa-02.md) y [fuente PlantUML](etapa-02-flujo-principal.puml). Registrar cualquier comprobación de renderización no ejecutada como pendiente técnico.

### ETAPA 03 — Ingeniería de requisitos · APROBADA

**Objetivo:** convertir el alcance y los flujos en una especificación verificable **por módulo**, no organizada artificialmente por pantallas.

- Mantener **40 RF**, criterios de aceptación Dado–Cuando–Entonces, **11 RNF**, RN y prioridades MoSCoW.
- Definir permisos, estados, condiciones y resultados observables; incluir casos negativos de stock, autorizaciones, anticipo y cierre.
- Conservar identificadores estables y pendientes expresos sin inventar valores, integraciones ni nuevas reglas.

**Entregable/cierre:** [RN/RNF y prioridades](etapa-03.md) y [catálogo de RF/CA](etapa-03-requisitos.md) aprobados como línea base documental.

### ETAPA 04 — Modelado del sistema · APROBADA POR EL USUARIO (2026-10-20)

**Objetivo:** expresar las funcionalidades e interacciones entre actores y sistema mediante **diagramas de casos de uso UML**, sin fijar arquitectura ni tablas.

- Mantener un **CU general (CU-00)** y **7 CU modulares (CU-01 a CU-07)**. Esta etapa no requiere diagramas de secuencia ni de actividades.
- Mantener **8 fuentes PlantUML** y trazabilidad **40/40 RF → casos de uso**, verificando permisos, rechazo, stock, anticipo y cierre sin agregar funciones.
- Revisar asociaciones de roles y decisiones pendientes; **compilar y renderizar** realmente los diagramas.

**Entregable:** [modelo y matriz de trazabilidad](etapa-04.md), [diagramas](diagramas/etapa-04/).  
**Aprobación expresa:** registrada el 2026-10-20 para los 8 CU. **Verificaciones pendientes:** compilación/renderización de PlantUML, cotejo de la versión visual elegida de CU-00 y ratificación de responsables de M07; estos pendientes no implican su aprobación tácita.

### ETAPA 05 — Arquitectura de software · APROBADA (2026-10-20)

**Objetivo:** establecer límites y contratos técnicos antes de crear código.

- Documentar **Python + FastAPI**, **SQLAlchemy Async, asyncpg, Alembic, PostgreSQL y Docker**; monolito modular con **hexagonal + Vertical Slicing** y configuración sencilla en `main.py` + `core/`.
- Definir **API REST JSON**, JWT/Argon2, transacciones, permisos y simulaciones, sin detalles de implementación innecesarios.
- Definir organización Flutter propuesta: **customer_app** y **staff_app** (mozos, cocina y caja; panel administrativo **Flutter Web dentro de staff_app**), con responsabilidades compartidas sin tercera aplicación.
- Preparar Skills **restaurant-fastapi-slice** (backend) y **restaurant-flutter-slice** (frontend); mantener **AGENTS.md** breve, cargar solo el contexto/Skill pertinente y usar MCP bajo demanda.
- Evitar instalar FastAPI/Flutter, programar endpoints, crear tablas o migraciones durante esta etapa.

**Entregable:** [arquitectura y tecnologías de backend/frontend](etapa-05.md), más Skills en **.agents/skills/** de su respectivo repositorio. No se mantienen diagramas de arquitectura de ETAPA 05.  
**Aprobación expresa:** registrada el 2026-10-20. Las dos Skills pasaron validación estructural (2026-10-20); su invocación real en los IDE no se comprobó. Se conservan pendientes las decisiones funcionales abiertas.

### ETAPA 06 — Diseño de base de datos desde cero · APROBADA (2026-10-21)

**Objetivo:** convertir requisitos y contratos aprobados en un modelo PostgreSQL consistente; **aún sin crear la base de datos ejecutable**.

- Identificar entidades/relaciones de M01–M07, cardinalidades y propiedad de datos por módulo.
- Diseñar modelo entidad-relación, normalización, esquema lógico y físico, tipos, claves, restricciones e índices.
- Definir integridad de pedidos, estados, stock, permisos, anticipos, cobros y trazabilidad/auditoría.
- Especificar estrategia física para confirmación atómica, concurrencia de stock e idempotencia, respetando RNF-04/05/10.
- Revisar trazabilidad **RF/RN → entidades y restricciones**, y documentar decisiones sin incorporar ingredientes, sedes, logística u otras exclusiones.

**Entregable aprobado:** [diseño PostgreSQL y matriz RF 40/40](etapa-06.md), [DER editable](diagramas/etapa-06/etapa-06-der.drawio) y [vista SVG](diagramas/etapa-06/etapa-06-der.svg).  
**Aprobación expresa:** registrada el 2026-10-21 para el diseño documental de 14 tablas; pendientes funcionales documentados se mantienen sin ratificación. Edición visual en diagrams.net y pruebas con PostgreSQL no ejecutadas.

### ETAPA 07 — Configuración técnica · IMPLEMENTADA / PENDIENTE DE APROBACIÓN

**Objetivo:** convertir la arquitectura aprobada en proyectos ejecutables con infraestructura mínima reproducible.

- Inicializar **FastAPI**, SQLAlchemy Async, asyncpg, Alembic y **PostgreSQL** (Docker para desarrollo) según versiones verificadas.
- Crear estructura hexagonal/slices, configuración por entornos, secretos fuera del repositorio, dependencias, CORS, diagnóstico/healthcheck y registros básicos.
- Crear esquema y migraciones **iniciales** desde el modelo aprobado; validar conexión real y actualización desde base vacía.
- Inicializar workspace Flutter y **customer_app/staff_app**, configuración de API local/remota y herramientas de análisis y pruebas.
- Configurar base técnica de sesiones/autenticación y autorización, **sin implementar todavía los 40 RF completos**.

**Entregable implementado:** backend y aplicaciones base, migración reproducible, instrucciones y pruebas automáticas.

**Verificación:** PostgreSQL 17.11 en Docker Compose con healthcheck sano, upgrade/downgrade Alembic, API saludable, 23 pruebas backend, análisis/pruebas Flutter y builds Android/Web correctos. La aprobación de la etapa sigue siendo exclusiva del usuario.

### ETAPA 08 — Desarrollo del backend

**Objetivo:** implementar los **40 RF** de M01–M07 como casos de uso y contratos REST, respetando el comportamiento aprobado.

- Implementar accesos/roles, catálogo/stock, mesas, registro/aprobación de pedidos, cocina/comandas, caja/anticipos, atención/entregas y cierre.
- Garantizar transiciones autorizadas, verificación del 50 %, stock atómico y sin doble descuento, cobros idempotentes y bloqueo de operaciones inválidas.
- Implementar simulaciones explícitas y auditables; **no** integrar pagos reales, WhatsApp automático, GPS ni SUNAT sin nuevos requisitos.
- Incorporar validaciones, manejo de errores, OpenAPI, pruebas unitarias y de integración **contra PostgreSQL real de pruebas**.
- Mantener correspondencia **RF/CA → caso de uso → endpoint → prueba**.

**Entregable:** API documentada y funcional, migraciones incrementales pertinentes, matriz de cobertura y resultados verificables.  
**Cierre:** todos los RF del alcance implementados o señalados como pendientes aprobados; permisos, errores y flujos críticos pasan pruebas reproducibles.

### ETAPA 09 — Diseño UX/UI en Figma

**Objetivo:** diseñar interfaces coherentes con roles, RF y contratos reales, sin programarlas todavía.

- Definir sistema visual, componentes reutilizables, navegación, accesibilidad y estados loading/empty/error/success.
- Diseñar **app cliente** (cuenta/invitado, catálogo, mesa, pedido, seguimiento) y **app de personal** (mozo, cocina, caja, administración adaptativa).
- Cubrir aprobación/rechazo, stock insuficiente, anticipo pendiente, comanda y cierre; **identificar claramente acciones simuladas**.
- Construir prototipos de recorridos principales y revisar cada pantalla frente a RF, actor, permisos y API disponible/propuesta.

**Entregable:** archivo Figma organizado, componentes y prototipos validados, mapa **pantalla → RF/CA → API**.  
**Cierre:** aprobación visual/funcional; no diseñar acciones que carezcan de respaldo en requisitos. **Se abordará después de completar y verificar el backend en ETAPA 08**, siguiendo el orden backend primero y frontend después.

### ETAPA 10 — Desarrollo del frontend

**Objetivo:** transformar el diseño aprobado en las dos aplicaciones Flutter conectadas al backend.

- Implementar **customer_app** y **staff_app**, reutilizando paquetes justificados y respetando los slices definidos.
- Construir pantallas, estado, navegación por permisos, formularios, tratamiento de errores y persistencia segura de sesión.
- Consumir APIs reales con configuración por entorno; no duplicar reglas de negocio del servidor ni mostrar éxito sin respuesta confirmada.
- Implementar flujos de mozo, cocina, caja y administración junto con las tres modalidades del cliente.
- Probar widgets, navegación y estados críticos, incluido el uso en dispositivo Android; validar las pantallas adaptativas acordadas.

**Entregable:** apps operativas, vinculadas a API, con pruebas y matriz **RF/CA → pantalla → API**.  
**Cierre:** recorridos principales funcionan en los dispositivos objetivo y representan correctamente validaciones y simulaciones.

### ETAPA 11 — Integración, pruebas y entrega

**Objetivo:** demostrar funcionamiento de extremo a extremo y cerrar el proyecto académico con evidencia.

- Probar los recorridos completos: local por mozo/app, recojo por app/canal externo y delivery por app/canal externo.
- Verificar permisos, excepciones, concurrencia de stock, pagos/anticipos simulados, idempotencia, saldos, comandas y cierre.
- Ejecutar pruebas unitarias, integración, funcionales, seguridad básica y rendimiento **según métricas aprobadas**.
- Validar backend con PostgreSQL y frontend en los dispositivos/entornos acordados; documentar incidencias y correcciones.
- Preparar instalación, configuración sin secretos, manual de demostración, evidencias y entrega académica.

**Entregable:** reporte de pruebas, incidencias resueltas o aceptadas, documentación final y demostración reproducible.  
**Cierre:** criterios de aceptación satisfechos y entrega expresamente aprobada.

## 4. Reglas de avance, trazabilidad y eficiencia

1. **Aprobación:** el usuario aprueba cada etapa; avanzar para redactar un borrador no supone aprobación. Antes de implementar decisiones de ETAPAS 04–05, revisar su estado y los pendientes que afectan el trabajo.
2. **Trazabilidad:** conservar la cadena **RN/RF/CA → UML → arquitectura → BD → API → interfaz → prueba**, con referencias específicas y sin cambiar identificadores por estética.
3. **Sin adelantar etapas:** ETAPA 06 diseña; ETAPA 07 inicializa y migra; ETAPA 08 implementa backend; ETAPA 09 diseña UI; ETAPA 10 implementa Flutter; ETAPA 11 integra y certifica el recorrido académico.
4. **Documentación:** usar **docs/** de ambos repositorios como fuente compartida y mantener iguales los documentos comunes. Cada etapa añade su documento y artefactos solo cuando aportan valor; conservar los archivos previamente aprobados.
5. **Agentes/tokens:** cargar **AGENTS.md + este índice + documento de la etapa**, y únicamente Skills, RF/diagramas o código pertinentes. Evitar lecturas completas repetidas, Skills duplicadas, MCP innecesarios y logs extensos.
6. **Validación honesta:** distinguir documento revisado, archivo verificado, compilación, ejecución de pruebas y aprobación; nunca marcar como hecha una comprobación no ejecutada.
7. **Control de cambios:** cambios de alcance, roles, políticas o simulaciones regresan a los documentos afectados y actualizan trazabilidad. No introducir funcionalidades extra como solución a una etapa técnica.

**Próximo hito:** revisar y, si corresponde, aprobar expresamente la [ETAPA 07 — Configuración técnica](etapa-07.md). No iniciar ETAPA 08 antes de esa decisión.
