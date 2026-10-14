# Restaurant App V2 — Reglas para Codex y AGY

## Estado y autoridad

- **ETAPAS 00–03 aprobadas (2026-10-13). ETAPA 04 en revisión y no aprobada. ETAPA 05 autorizada para elaboración, documentada como propuesta y no aprobada.** No aprobar etapas por inferencia.
- Índice oficial: `docs/etapas/README.md`. Trabajo actual: `docs/etapas/etapa-05.md`.
- Las ETAPAS 01–03 prevalecen como línea base de negocio y requisitos. ETAPA 04 es referencia UML provisional: no usarla para resolver RN-20/RN-21, RNF-08, responsables de M07 ni comprobantes.

## Carga selectiva

1. Leer este archivo, el índice y el documento de la etapa vigente.
2. Abrir solo los RF/RN/RNF y diagramas que afecten la tarea; no releer etapas completas si una referencia puntual basta.
3. Para un slice backend, cargar `.agents/skills/restaurant-fastapi-slice/SKILL.md` en el repositorio backend. Para Flutter, cargar `.agents/skills/restaurant-flutter-slice/SKILL.md` en el repositorio frontend. No cargar ambas Skills salvo trabajo transversal.
4. Los documentos compartidos se leen en un repositorio y se comparan por hash/diff con el otro; no cargar dos copias idénticas al contexto.

## Alcance seguro

- Mantener los siete módulos M01–M07 y las decisiones aprobadas. Distinguir siempre heredado, propuesto y pendiente.
- Durante ETAPA 05: documentar arquitectura, contratos, Skills y criterios. **No** instalar/inicializar Flutter o FastAPI, implementar APIs, crear tablas/migraciones ni agregar funcionalidades.
- Hacer cambios mínimos dentro de la etapa. No sobrescribir trabajo ajeno, registrar secretos, ejecutar commits/push/merge ni usar conectores externos sin necesidad.
- Mantener idénticos `docs/` compartidos entre backend y frontend. Las Skills específicas viven solo en su repositorio; ambos agentes usan el mismo `SKILL.md`.
- Usar archivos y Git locales primero. GitHub se reserva para operaciones remotas solicitadas; Figma para ETAPA 09; otros MCP requieren una necesidad vigente.

## Verificación y cierre

- Confirmar repositorio y rama `develop`, revisar cambios existentes y validar enlaces, trazabilidad y diferencias entre repositorios.
- Reportar archivos modificados, comprobaciones reales, riesgos y pendientes. No presentar inspección documental como prueba de ejecución.
- La aprobación de una etapa corresponde exclusivamente al usuario.

Procedimiento operativo ampliado: `docs/agentes/README.md`.
