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

Establecer cómo funcionará el restaurante, qué problemas resolveremos, los actores, las modalidades de consumo y las funcionalidades incluidas o simuladas.

## ETAPA 02 — Definición de flujos del negocio

Diseñar los flujos de clientes, mozos, cocina, caja y administración, incluyendo las modalidades de consumo en mesa, recojo en tienda y delivery.

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
