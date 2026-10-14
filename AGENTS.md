# Restaurant App V2 — Reglas para Codex y AGY

## Estado y fuentes
- **Etapa vigente: 00 — EN CURSO, no aprobada.** No avanzar a otra etapa sin aprobación expresa del usuario.
- Índice oficial: `docs/etapas/README.md`. Trabajo actual: `docs/etapas/etapa-00.md`.
- Procedimiento operativo: `docs/agentes/README.md`. Consultar solo los documentos pertinentes para la tarea.

## Trabajo seguro y eficiente
1. Antes de modificar, identificar repositorio, rama (`develop`), etapa y archivos afectados; revisar contenido y cambios existentes.
2. Hacer cambios mínimos y acotados. Evitar búsquedas o lecturas masivas, repetir contexto, generar archivos redundantes y mostrar logs extensos.
3. No inventar acuerdos, requisitos, reglas de negocio ni aprobaciones. Distinguir `confirmado`, `propuesto` y `pendiente`.
4. Mantener `docs/` sincronizada entre backend y frontend para los documentos compartidos; indicar archivos modificados y validaciones realizadas.
5. No sobrescribir trabajo ajeno ni modificar simultáneamente el mismo archivo con dos agentes. No hacer push, merges o cambios destructivos no solicitados.
6. Nunca registrar contraseñas, claves, tokens o información sensible; usar MCP solo si es necesario y está autorizado.

## Restricciones de la ETAPA 00
- **Prohibido** instalar frameworks, inicializar Flutter/FastAPI, crear APIs, migraciones, esquema de BD o funcionalidades.
- No reutilizar como vigentes decisiones, diagramas o código de versiones anteriores.
- Definir Skills técnicas y reglas de arquitectura en ETAPA 05; ahora solo documentar la estrategia.
- Si una tarea excede esta etapa, señalarla como pendiente y no implementarla.

## Cierre de cada tarea
Reportar brevemente: qué cambió, rutas, pruebas verificadas, pendientes y estado de aprobación. No declarar una prueba ejecutada si solo se verificó documentación.
