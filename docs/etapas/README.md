# Plan maestro de desarrollo — Restaurant App V2

**Estado a 2026-10-13:** **ETAPAS 00, 01, 02 y 03 APROBADAS POR EL USUARIO.** ETAPA 04 elaborada y **pendiente de aprobación**; ETAPAS 05–11 aún no aprobadas. Los acuerdos explícitamente marcados como pendientes no se convierten por ello en decisiones ratificadas.

## ETAPA 00 — Configuración de agentes de IA

**Empezamos aquí.**

Definir y configurar las herramientas para que Codex y AGY trabajen coordinadamente y consuman los mínimos tokens necesarios.

- **00.1.** Estrategia de ahorro de tokens.
- **00.2.** Reglas compartidas mediante `AGENTS.md`.
- **00.3.** Skills, documentación modular, MCP y gestión del contexto.
- **00.4.** Validación de configuración en ambos repositorios.

No instalar frameworks ni implementar funcionalidades todavía. Las Skills especializadas se completarán cuando conozcamos la arquitectura.

## ETAPA 01 — Análisis del negocio y alcance

Definir desde cero el funcionamiento de **Chifa ASIA**, un restaurante sin sedes: problemática y objetivos; seis actores (**cliente, mozo, cajero, administrador, personal de cocina y superadministrador**); responsabilidades, roles acumulativos, tres modalidades y siete módulos funcionales esenciales, incluido el **catálogo de productos con control de stock**.

Acordar el recorrido del pedido de recepción a entrega/cobro, sin definir todavía diagramas ni requisitos formales:
- **Consumo en local:** pedido por mozo (envío directo a cocina) o por app con mesa seleccionada y aprobación del Mozo o Administrador tras verificarla presencialmente.
- **Recojo en local y delivery:** pedidos por app (aprobación del Administrador) o por llamada/WhatsApp (registro y validación del Administrador); el Administrador verifica **anticipo del 50 % antes de cocina**.
- **Stock:** cantidades por producto, descuento automático al confirmar el pedido y disponibilidad editable por el Administrador.
- **Cocina:** comandas y estados de preparación a cargo del personal de cocina.
- **Delivery:** sin gestión de repartidores ni logística de rutas.

Clasificar funcionalidades incluidas, simuladas/manuales y excluidas. Postergar detalles secundarios que no afecten el flujo principal.

## ETAPA 02 — Flujo principal y subflujos del negocio

Diseñar **un único flujo principal de extremo a extremo**, iniciado cuando un cliente desea hacer un pedido, con rombos para elegir modalidad y canal:
1. **Consumo en local:** mozo o app.
2. **Recojo en local:** app, llamada o WhatsApp.
3. **Delivery:** app, llamada o WhatsApp.

Unificar registro, aprobaciones según modalidad, anticipo obligatorio del 50 % para recojo/delivery antes de cocina, descuento de stock al confirmar, preparación de comandas, servicio o entrega, cobro restante y cierre. Crear solo los subflujos necesarios para comprender actores, decisiones y excepciones esenciales; no diagramar logística de repartidores.

## ETAPA 03 — Ingeniería de requisitos

Definir requisitos funcionales, no funcionales, reglas de negocio, prioridades y criterios de aceptación a partir de los flujos aprobados.

## ETAPA 04 — Modelado del sistema

Elaborar diagramas de casos de uso UML, diagramas de actividades, secuencias y relaciones entre actores y funcionalidades.

## ETAPA 05 — Arquitectura de software

Definir aplicaciones Flutter, roles, panel administrativo, módulos del backend, comunicación REST, arquitectura hexagonal y Vertical Slicing. Aquí consolidaremos las Skills técnicas.

## ETAPA 06 — Diseño de base de datos desde cero

Desarrollar el modelo entidad-relación, normalización, tablas, relaciones, restricciones, índices y diseño físico de PostgreSQL.

## ETAPA 07 — Configuración técnica

Inicializar FastAPI, SQLAlchemy Async, asyncpg, Alembic, conexión PostgreSQL, autenticación y estructura de Flutter. Crear las primeras migraciones.

## ETAPA 08 — Desarrollo del backend

Implementar los módulos, APIs REST, validaciones, permisos, operaciones de negocio y simulaciones de servicios externos.

## ETAPA 09 — Diseño UX/UI en Figma

Diseñar y validar pantallas, componentes visuales, navegación y prototipos de las aplicaciones. Esta etapa puede comenzar en paralelo con el backend cuando los flujos estén aprobados.

## ETAPA 10 — Desarrollo del frontend

Implementar las interfaces Flutter para clientes y personal, el panel administrativo acordado y el consumo de las APIs.

## ETAPA 11 — Integración, pruebas y entrega

Ejecutar pruebas unitarias, integración y flujos completos; verificar simulaciones, corregir errores y preparar la demostración académica.
