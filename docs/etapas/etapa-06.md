# ETAPA 06 — Diseño de base de datos | Chifa ASIA

**Estado:** INICIADA / PENDIENTE DE DISEÑO, REVISIÓN Y APROBACIÓN  
**Inicio:** 2026-10-20  
**Alcance:** diseñar la base de datos PostgreSQL para los módulos M01–M07. **No ejecutar SQL, crear tablas ni migraciones** en esta etapa.

## 1. Fuentes obligatorias

- [ETAPA 01 — Negocio y alcance](etapa-01.md): siete módulos, seis actores y tres modalidades.
- [ETAPA 02 — Flujo principal](etapa-02.md): registro, revisión, stock, anticipo, cocina, cobro y entrega.
- [ETAPA 03 — Requisitos](etapa-03-requisitos.md) y [resumen de RN/RNF](etapa-03.md): **40 RF**, 11 RNF y reglas aprobadas.
- [ETAPA 04 — Casos de uso](etapa-04.md): entregable aprobado, observaciones y permisos aún pendientes.
- [ETAPA 05 — Arquitectura](etapa-05.md): monolito modular, hexagonal + Vertical Slicing, PostgreSQL, SQLAlchemy Async y Alembic.

## 2. Trabajo de esta etapa

1. Identificar los datos necesarios para **cada RF**, sin añadir funcionalidades nuevas.
2. Definir entidades, atributos esenciales, relaciones y cardinalidades de M01–M07.
3. Asignar propiedad de datos a cada módulo; permitir referencias entre módulos sin duplicar entidades.
4. Diseñar el modelo lógico relacional: claves primarias/foráneas, restricciones, nulabilidad e índices justificados.
5. Definir el modelo físico PostgreSQL y la estrategia **propuesta** de transacciones y concurrencia: confirmar pedidos, descontar stock exactamente una vez, registrar un único anticipo simulado y una comanda por confirmación.
6. Validar estados, permisos y trazabilidad **RF/RN/CA → datos** con los tres recorridos: local, recojo y delivery.
7. Documentar decisiones pendientes y obtener aprobación expresa **antes** de implementar migraciones en ETAPA 07.

## 3. Restricciones y decisiones abiertas

- Conservar los **siete módulos** y sus 40 RF. No diseñar sedes, ingredientes, recetas, almacenes, repartidores, rutas ni GPS.
- Los pagos y anticipos son simulados. **Comprobantes simulados** fueron autorizados como decisión de alcance, pero su emisión necesita requisitos y criterios de aceptación específicos **antes de modelar nuevas entidades**; sin integración SUNAT ni validez tributaria.
- Roles acumulativos y acceso global del Superadministrador. Verificar anticipo no concede permiso general de Caja.
- Mantener **RN-20 y RN-21** pendientes de ratificación formal, así como responsables de recojo, delivery y cierre (M07) y métrica RNF-08. La arquitectura técnica no aprueba estos puntos por inferencia.
- Mantener el diseño de base de datos separado de código FastAPI, Flutter y migraciones ejecutables.

## 4. Entregables y criterios de cierre

- Modelo conceptual y modelo lógico de PostgreSQL para los siete módulos.
- Modelo físico propuesto: tablas y relaciones previstas, tipos, restricciones e índices justificados **en documentación**, no creados en PostgreSQL.
- Estrategia documentada de transacción única, concurrencia de stock, pagos simulados e idempotencia.
- Matriz de trazabilidad entre datos y los 40 RF, sin cambios a sus identificadores.
- Registro de decisiones pendientes y validaciones **realmente realizadas**.
- **Aprobación expresa del usuario** para finalizar la ETAPA 06.

**Estado final:** ETAPA 06 INICIADA, NO APROBADA. No se ha diseñado todavía el esquema de datos ni ejecutado migraciones.
