# ETAPA 08 — Informe final de auditoría integral del backend (08.10)

**Fecha:** 2026-10-22 · **Rama y HEAD al iniciar:** `develop` / `210ae896963463e60ed569f5fa53515ea6e7a708` · **Estado:** verificación técnica terminada; aprobación de la ETAPA 08 reservada al usuario. El árbol estaba limpio al comenzar; los cambios de 08.10 permanecen locales, sin commit ni push. Se auditó exclusivamente `/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2`.

## Alcance y cobertura

La especificación aprobada en [`etapa-03-requisitos.md`](etapa-03-requisitos.md) contiene **40 RF y 48 CA**. Un cotejo de identificadores contra la [matriz de trazabilidad](etapa-08-progreso.md#3-matriz-de-trazabilidad-actualizar-por-rf-realmente-verificado) confirma **40/40 RF y 48/48 CA explícitos**, enlazados allí con caso de uso, contrato REST y prueba. Se comprobó la API y persistencia del backend, no las pantallas Flutter ni el despliegue público.

| Módulo | RF / CA | Evidencia principal reejecutada en 08.10 | Resultado backend |
|---|---:|---|---|
| M01 Usuarios/accesos | 5 / 7 | `test_m01_access.py`, `test_m04_requests.py`, `test_m08_integral_audit.py`; JWT/Argon2, invitado, seis roles, roles acumulados, denegaciones y Super Administrador operando M01–M07 | 5/5 RF; 7/7 CA |
| M02 Catálogo/stock | 6 / 7 | `test_m02_catalog.py`, `test_m04_confirm_order.py`; disponibilidad, stock 10→8, pendiente sin descuento, carrera por última unidad y sin duplicación | 6/6 RF; 7/7 CA |
| M03 Mesas | 4 / 4 | `test_m03_tables.py`, `test_m04_requests.py`, `test_m08_integral_audit.py`; listado, vínculo al pedido, ocupación/liberación autorizada y auditada | 4/4 RF; 4/4 CA |
| M04 Pedidos | 11 / 14 | `test_m04_requests.py`, `test_m04_confirm_order.py`, `test_m07_fulfillment.py`; tres modalidades, canales, snapshots, aprobación presencial, rechazo, ConfirmOrder y seguimiento | 11/11 RF; 14/14 CA |
| M05 Cocina | 4 / 5 | `test_m05_kitchen.py`, `test_m04_confirm_order.py`, `test_m07_fulfillment.py`; comanda solo de confirmado, líneas, preparación y `READY` antes de atender | 4/4 RF; 5/5 CA |
| M06 Anticipo/Caja | 6 / 6 | `test_m06_advances.py`, `test_m06_collections.py`, `test_m06_payment_methods.py`, `test_m07_fulfillment.py`; 50 % redondeado, cuatro medios simulados, saldo y bloqueo de cierre | 6/6 RF; 6/6 CA |
| M07 Cumplimiento/cierre | 4 / 5 | `test_m07_fulfillment.py`, `test_m08_integral_audit.py`; servido, recojo, delivery, cierre con atención/entrega y saldo cero | 4/4 RF; 5/5 CA |
| **Total** | **40 / 48** | **Suite integral con PostgreSQL real** | **40/40 RF; 48/48 CA como contratos backend** |

Los CA que describen una interacción en la app (por ejemplo, selección de mesa o visualización del estado) se verificaron **a través de la API**, no como interfaz Android/Web. Esa validación de UI pertenece a las etapas posteriores; la tabla no pretende certificar el producto extremo a extremo.

## Seguridad, integraciones y consistencia

- **Permisos M07 decididos por el usuario:** Mozo registra `SERVED` en local; Administrador registra `PICKED_UP`, `DELIVERED` y cierre; Super Administrador puede ejecutar todas esas operaciones. Administrador **no** obtiene permiso de Cajero por verificar un anticipo o registrar entrega. La prueba nueva `test_m08_integral_audit.py` demostró con un mismo Super Administrador la operación real de M01–M07 en PostgreSQL, incluido el permiso de Mozo/Cocina/Cajero por bypass. No se añadió rol de repartidor ni logística.
- **Control de acceso:** la suite ejercita 401/403 para credenciales/roles inválidos, 404 para pedidos de otro cliente, 409 para conflictos de estado, stock, saldo o llave repetida con payload distinto, y 422 para datos inválidos. Se inspeccionaron las 40 operaciones REST en 35 patrones de ruta OpenAPI: `BearerAuth` figura en las protegidas; las siete escrituras críticas de confirmación, anticipo, cobro, servido, recojo, entrega y cierre declaran `Idempotency-Key` obligatorio. M01 resuelve roles/sesión contra la BD; la autorización de casos de uso no depende solo del router.
- **Contratos/arquitectura:** inspección estática de 200 archivos Python de M01–M07: **cero imports de adaptadores o dominio internos de otro módulo** y **cero referencias a FastAPI/Pydantic/SQLAlchemy en `domain/`**. Las integraciones M04↔M02/M05/M06, M06↔M07 y M07↔M04/M05/M06 usan contratos `public.py` y la sesión transaccional compartida.
- **Transacciones, idempotencia y carreras:** las pruebas PostgreSQL existentes reejecutadas cubren solicitud simultánea con misma llave, ConfirmOrder con dos sesiones sobre último stock, dos mozos en mesas distintas sobre un producto sin deadlock, rollback ante conflicto de comanda, dos cajeros compitiendo por saldo, reintento concurrente de cobro/anticipo, cumplimiento simultáneo, cierre simultáneo y rollback del cierre si falla la persistencia idempotente. La tercera lectura comprueba ausencia de dobles efectos. El flujo remoto real registra 50 % antes de cocina y saldo exacto solo después de `PICKED_UP`/`DELIVERED`.
- **Persistencia:** la base desechable migró desde vacío hasta `20261022_0004`; PostgreSQL mostró 14 tablas de aplicación, seis roles semilla y la tabla técnica `alembic_version`, sin drift detectado por Alembic. No se añadieron tablas ni migraciones en 08.10.

## Ejecución y resultados reales

Se creó únicamente `restaurant_m08_integral_codex_test` en el contenedor preexistente `postgres`, después de constatar que ese nombre no existía. `TEST_DATABASE_DSN` apuntó a esa base y `ALLOW_DESTRUCTIVE_TEST_DATABASE` coincidió exactamente con su nombre; ninguna prueba destructiva apuntó a `restaurant_app` ni a otras bases preexistentes.

| Comprobación | Resultado |
|---|---|
| `pytest tests/ -q --no-cov --tb=short` con PostgreSQL aislado | **148 passed en 76.10 s**; 57 integraciones y 91 pruebas no marcadas como integración |
| Nueva prueba transversal M01–M07 | **1 passed**; no encontró un defecto de permisos |
| `ruff check src tests alembic` / `ruff format --check src tests alembic` | Sin hallazgos; 244 archivos formateados tras añadir la prueba |
| `mypy src` | Sin errores en 211 archivos fuente |
| `alembic upgrade head` / `alembic check` | Upgrade `0001→0004` correcto; **No new upgrade operations detected** |
| OpenAPI generado | 35 patrones de ruta, 40 operaciones; esquema `BearerAuth` y siete operaciones críticas con llave obligatoria |
| `git diff --check` | Sin errores |

`alembic check` emite la advertencia ya conocida y no fatal `Can't validate argument 'dialect_options'` al reflejar el `CHECK NOT VALID` de pagos de 08.08; no reporta diferencias de esquema. La comprobación inicial de formato de la prueba nueva falló por estilo y se corrigió con Ruff antes de la suite final; no hubo fallo funcional. Antes de retirar la base se verificó su nombre exacto, revisión `20261022_0004`, 14 tablas de aplicación, seis roles, cero filas en las otras 13 tablas y cero conexiones ajenas. La base temporal fue eliminada y se confirmó su ausencia; es recreable mediante migraciones.

## Hallazgos, límites y recomendación

1. **Trazabilidad corregida:** la matriz anterior omitía RF-M05-02 y abreviaba siete identificadores de CA. Ahora enumera **40 RF y 48 CA** sin faltantes. CA-M01-05-01 estaba marcado parcial: la nueva prueba transversal cierra su evidencia backend. No se detectó un defecto de código que justificara cambiar reglas o casos de uso existentes.
2. **Permisos/documentación corregidos:** `AGENTS.md`, el índice, el plan y la bitácora todavía llamaban «pendientes» a los permisos M07 aprobados en 08.09 y conservaban estados antiguos. Se actualizaron sin reescribir la especificación histórica de ETAPA 03 ni añadir permisos.
3. **Pendientes no ocultos:** RN-20 y RN-21 conservan la ratificación pendiente de su **redacción**; los comportamientos de no sobreventa y cierre pagado/entregado ya están exigidos por RF/CA aprobados y probados. RNF-08 aún no tiene umbral aprobado; no se inventó ni ejecutó un benchmark para certificarlo. HTTPS de despliegue (RNF-03), desconexión/interfaz móvil (RNF-07/10) y comprobantes sin RF/CA requieren validación o decisiones en su etapa/entorno pertinente. No se verificó una implantación de producción ni pantallas Flutter.

**Calificación técnica del backend 08.10: 9/10.** La trazabilidad completa, 148 pruebas verdes en PostgreSQL real, controles de autorización, rollback y concurrencia sustentan la recomendación de **aprobar la ETAPA 08 como backend implementado**, no como sistema desplegado o producto con frontend validado. No se asigna 10/10 porque HTTPS operativo, rendimiento con umbral aprobado y experiencia/desconexión de cliente no tienen evidencia en esta etapa. La aprobación final corresponde exclusivamente al usuario; no iniciar ETAPA 09 por inferencia.
