# ETAPA 07 — Configuración técnica | Chifa ASIA

**Estado:** INICIADA / PENDIENTE DE IMPLEMENTACIÓN, VERIFICACIÓN Y APROBACIÓN  
**Fecha de inicio:** 2026-10-21 · **Rama:** `develop`  
**Base aprobada:** ETAPA 05 (arquitectura) y ETAPA 06 (diseño PostgreSQL, 14 tablas/DER). La ETAPA 07 prepara una infraestructura **ejecutable y reproducible**; no implementa los 40 RF, que corresponden a ETAPA 08.

## 1. Objetivo

Inicializar los proyectos y comprobar que backend, base de datos y las dos aplicaciones Flutter pueden arrancar en entornos de desarrollo, sin adelantar funcionalidades del negocio.

## 2. Alcance técnico

**Backend primero:**
1. Verificar el repositorio, rama `develop`, estructura y herramientas ya existentes; conservar trabajo previo y no reinicializar proyectos operativos.
2. Configurar Python + FastAPI con `main.py`, `core/` y módulos M01–M07 según la arquitectura hexagonal + Vertical Slicing aprobada; crear solo los puntos de entrada y dependencias mínimos, no implementar casos de uso.
3. Preparar PostgreSQL en Docker para desarrollo, variables de entorno y secretos fuera de Git, conexión SQLAlchemy Async mediante `asyncpg`, Alembic y diagnóstico de disponibilidad.
4. Crear los modelos ORM y las migraciones iniciales de las 14 tablas **conforme al diseño de ETAPA 06**, incluyendo claves, restricciones e índices que puedan implementarse sin adoptar decisiones pendientes. Documentar incompatibilidades antes de modificar el diseño aprobado.
5. Verificar migración sobre base vacía y esquema resultante, arranque de API y conexión real; agregar pruebas de humo reproducibles.

**Frontend mínimo, sin funciones de negocio:**
6. Comprobar/configurar workspace Flutter y `customer_app` (Android), `staff_app` (Android + Flutter Web), sin tercera aplicación ni paquetes compartidos prematuros.
7. Configurar entornos API, análisis estático y arranque de ambas aplicaciones, sin pantallas funcionales del negocio, flujos de compra ni integración completa con la API.
8. Mantener el orden de ejecución: el **desarrollo funcional backend (ETAPA 08)** debe terminar y validarse **antes del diseño UX/UI (ETAPA 09)** y del desarrollo Flutter (ETAPA 10).

## 3. Restricciones

- Mantener un solo restaurante, siete módulos M01–M07, 40 RF, 11 RNF y roles aprobados.
- No crear funciones adicionales, módulos nuevos, pasarelas reales, facturación SUNAT, WhatsApp automático, GPS, inventario de ingredientes ni logística de repartidores.
- Respetar las reglas de integridad, anticipo 50 % redondeado al céntimo superior, saldos derivados y estructura de las 14 tablas aprobadas en ETAPA 06.
- Mantener como pendientes de decisión los responsables M07, redacciones RN-20/RN-21, métrica RNF-08, requisitos específicos de emisión de comprobantes simulados y detalles técnicos aún propuestos.
- No convertir decisiones pendientes en permisos, estados o lógica funcional definitivos.
- Usar Skills especializadas solamente cuando proceda; en ETAPA 07 se configura infraestructura, no se implementan slices de ETAPA 08/10.
- No hacer commits ni push sin instrucción explícita para esas acciones de implementación.

## 4. Entregables y criterios de revisión

- Backend FastAPI mínimo que arranca, configuraciones por entorno y PostgreSQL Docker conectado.
- Modelos SQLAlchemy Async y migración Alembic inicial de acuerdo con el diseño aprobado, sin datos de negocio inventados.
- Evidencia reproducible de migración desde base vacía, restricciones, conexión y salud de la API.
- `customer_app` y `staff_app` inicializadas/validadas para las plataformas correspondientes; resultados de `flutter analyze` o limitaciones claramente registradas.
- Documentación de ejecución local y pruebas realmente realizadas, con comandos y resultados relevantes (sin secretos).
- Matriz de correspondencia entre las 14 tablas aprobadas, ORM y migraciones; pendientes no resueltos señalados.
- **Aprobación expresa del usuario** para cerrar ETAPA 07.

**Estado final:** ETAPA 07 INICIADA / NO APROBADA. Este documento define tareas y controles; **no afirma que se haya instalado software, arrancado servicios o ejecutado migraciones**.
