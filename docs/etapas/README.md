# Plan maestro de desarrollo — Restaurant App V2

## ETAPA 00 — Configuración de agentes de IA

**Empezamos aquí.**

Definir y configurar las herramientas para que Codex y AGY trabajen coordinadamente y consuman los mínimos tokens necesarios.

- **00.1.** Estrategia de ahorro de tokens.
- **00.2.** Reglas compartidas mediante `AGENTS.md`.
- **00.3.** Skills, documentación modular, MCP y gestión del contexto.
- **00.4.** Validación de configuración en ambos repositorios.

No instalar frameworks ni implementar funcionalidades todavía. Las Skills especializadas se completarán cuando conozcamos la arquitectura.

## ETAPA 01 — Análisis del negocio y alcance

Definir desde cero el funcionamiento de **Chifa ASIA** como un solo restaurante, sin sedes: problemas y objetivos del negocio, actores (**cliente, mozo, cajero, administrador y superadministrador**), responsabilidades, modalidades de consumo (**en local, recojo en local y delivery**) y funcionalidades incluidas, simuladas o excluidas.

Acordar solo las decisiones necesarias para representar el recorrido real del pedido, desde su recepción hasta su entrega y cobro. Considerar estos canales:
- **Consumo en local:** atención y registro del pedido por el mozo, o pedido del cliente desde la aplicación seleccionando su mesa.
- **Recojo en local y delivery:** pedido por aplicación, llamada o WhatsApp. Los pedidos recibidos por llamada o WhatsApp los registra el administrador.
- **Pedidos desde la aplicación:** requieren revisión y aprobación del personal autorizado; en consumo en local se comprueba presencialmente que el cliente ocupa la mesa indicada.
- **Recojo y delivery:** exigir confirmación del anticipo del **50 %** antes de enviar el pedido a cocina.

Las decisiones operativas secundarias se dejan para cuando afecten un flujo esencial. No diseñar todavía diagramas, requisitos ni arquitectura.

## ETAPA 02 — Flujo principal y subflujos del negocio

Diseñar **un único flujo principal de extremo a extremo** para Chifa ASIA, iniciado cuando el cliente desea realizar un pedido, con decisiones (rombos) para escoger:
1. **Consumo en local:** atención por mozo o pedido desde la app.
2. **Recojo en local:** pedido por app, llamada o WhatsApp.
3. **Delivery:** pedido por app, llamada o WhatsApp.

Unificar los caminos en los puntos que correspondan: registro del pedido, validación/aprobación cuando aplique, **anticipo confirmado del 50 % para recojo y delivery antes de cocina**, preparación, entrega y cierre.

Complementar el flujo principal únicamente con subflujos necesarios para aclarar responsabilidades de cliente, mozo, administración, caja y cocina, sin llenar el análisis de casos secundarios. Validar que ningún camino omita la aprobación o el anticipo exigidos y que los pasos sean coherentes con las decisiones de la ETAPA 01.

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
