# ETAPA 08 — Registro de continuidad Codex / AGY

**Estado inicial:** SIN BLOQUES FUNCIONALES VERIFICADOS. Actualizar después de cada bloque o antes de agotar contexto.  
**Plan estable:** [`etapa-08.md`](etapa-08.md) · **Rama:** `develop` · **RF oficiales:** `etapa-03-requisitos.md`.

## 1. Tablero de bloques

Estados permitidos: `PENDIENTE`, `EN CURSO`, `BLOQUEADO`, `IMPLEMENTADO SIN VERIFICAR`, `VERIFICADO`. No marcar `VERIFICADO` sin resultados concretos.

| Bloque | Responsable sugerido | Estado | RF validados | Evidencia | Siguiente dependencia |
|---|---|---|---|---|---|
| 08.00 Línea base | Codex | PENDIENTE | — | — | 08.01 |
| 08.01 M01 Accesos | Codex | PENDIENTE | — | — | 08.02 |
| 08.02 M02 Catálogo | AGY | PENDIENTE | — | — | 08.03 |
| 08.03 M03 Mesas | Codex | PENDIENTE | — | — | 08.04 |
| 08.04 M04 Solicitudes | AGY | PENDIENTE | — | — | 08.05 |
| 08.05 M06 Anticipo | Codex | PENDIENTE | — | — | 08.06 |
| 08.06 M05 Cocina base | AGY | PENDIENTE | — | — | 08.07 |
| 08.07 ConfirmOrder | Codex | PENDIENTE | — | — | 08.08 |
| 08.08 M06 Caja | AGY | PENDIENTE | — | — | 08.09 |
| 08.09 M07 + seguimiento | Codex | PENDIENTE | — | — | 08.10 |
| 08.10 Validación integral | AGY | PENDIENTE | — | — | Revisión usuario |

## 2. Último punto de control (actualizar SIEMPRE)

- **Fecha / agente:** sin ejecución registrada.
- **Bloque activo:** 08.00.
- **Estado del bloque:** PENDIENTE.
- **Directorio/repo y rama comprobados:** no comprobados en esta sesión.
- **Archivos afectados desde el último checkpoint:** ninguno documentado.
- **RF/CA implementados y verificados:** ninguno documentado.
- **API/slices terminados:** ninguno documentado.
- **Migraciones y estado Alembic:** revisar `alembic current` antes de empezar; no suponer estado de una BD local.
- **Pruebas ejecutadas (comando → resultado):** ninguna documentada en ETAPA 08.
- **Fallos conocidos/bloqueos:** autorizaciones M07, RN-20/RN-21, RNF-08 y emisión de comprobantes conservan estatus documental pendiente; confirmar impacto solo en los RF que toquen.
- **Revisión de otro agente:** pendiente.
- **Siguiente acción exacta:** auditar estado local (`git status`, app, ORM, migraciones/pruebas 07), registrar baseline, iniciar 08.01 solo después del gate 08.00.
- **Commit/push:** NO autorizado de forma automática; no inventar hash de trabajo sin commit.

## 3. Matriz de trazabilidad (actualizar por RF realmente verificado)

| RF / CA | Bloque | Caso de uso / slice | Endpoint REST | Pruebas ejecutadas | Resultado |
|---|---|---|---|---|---|
| _Sin cobertura de ETAPA 08 registrada_ | — | — | — | — | PENDIENTE |

**Regla:** agregar filas conforme avance cada bloque, referenciando identificadores exactos `RF-Mxx-yy` y `CA-Mxx-yy-zz` de ETAPA 03. No copiar los 40 RF completos aquí ni duplicar pruebas; enlazar rutas y comandos relevantes. Un RF asignado a un bloque no equivale a un RF probado.

## 4. Reglas de traspaso de agentes

1. Antes de dejar el trabajo por límite de tokens, escribir el punto de control con los archivos sin terminar, error/hipótesis comprobada y **una acción siguiente**; conservar `EN CURSO` si corresponde.
2. El nuevo agente lee este documento primero, consulta plan **solo bloque activo**, Skill backend y RF/CA pertinentes. Verifica `git status`; si el código no coincide, corrige el registro antes de escribir nuevo código.
3. El implementador es el único que modifica archivos de su bloque; el otro realiza revisión secuencial y registra riesgos. No mezclar cambios en el mismo directorio/archivo a la vez.
4. Tras una verificación real, actualizar tabla de bloques y matriz RF/CA. Nunca reportar `HECHO` por compilación incompleta o prueba no ejecutada.
5. Mantener esta bitácora y `etapa-08.md` idénticas en `docs/etapas/` de **ambos repositorios**. No realizar commit/push sin orden expresa del usuario.

## 5. Prompts mínimos de sesión

**Codex (implementar):** «Retoma Chifa ASIA ETAPA 08 desde `docs/etapas/etapa-08-progreso.md`. Consulta el bloque activo de `etapa-08.md`, la Skill `restaurant-fastapi-slice` y solo RF/CA relevantes. Verifica código y Git. Implementa y prueba únicamente el bloque actual. Actualiza checkpoint y detente.»

**AGY (revisar o tomar turno):** «Lee `docs/etapas/etapa-08-progreso.md` y el bloque activo. Como revisor, audita RF/CA, arquitectura hexagonal, permisos, integración PostgreSQL y pruebas sin editar archivos del implementador. Si es tu turno, implementa solo el bloque asignado y registra los resultados antes de entregar el control.»
