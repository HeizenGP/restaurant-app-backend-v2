# Restaurant App V2 — Reglas para Codex y AGY

## Estado y autoridad

- **ETAPAS 00–03 aprobadas (2026-10-13) y ETAPA 04 aprobada expresamente por el usuario (2026-10-20), con comprobaciones técnicas pendientes. ETAPA 05 aprobada expresamente (2026-10-20). ETAPA 06 aprobada expresamente como diseño documental (2026-10-21), con decisiones de negocio abiertas. ETAPA 07 implementada técnicamente y pendiente de revisión/aprobación; ETAPA 08 no iniciada.** No aprobar etapas por inferencia.
- Índice oficial: `docs/etapas/README.md`. Trabajo actual: `docs/etapas/etapa-07.md`.
- Las ETAPAS 01–03 prevalecen como línea base de negocio y requisitos. ETAPA 04 es línea base documental de casos de uso aprobada, pero no resuelve por sí sola RN-20/RN-21, RNF-08, responsables de M07 ni comprobantes.

## Carga selectiva

1. Leer este archivo, el índice y el documento de la etapa vigente.
2. Abrir solo los RF/RN/RNF y diagramas que afecten la tarea; no releer etapas completas si una referencia puntual basta.
3. **Skills técnicas bajo demanda:** activar `restaurant-fastapi-slice` solo para diseñar/revisar un caso de uso del backend (implementación desde ETAPA 08), y `restaurant-flutter-slice` solo para una funcionalidad Flutter (implementación desde ETAPA 10). Durante ETAPA 06, diseñar la BD sin activar Skills de implementación; en ETAPA 07, configurar herramientas sin adelantar funcionalidades. Cada Skill vive en `.agents/skills/<nombre>/SKILL.md` de su respectivo repositorio. No cargar ambas salvo revisión transversal.
4. Los documentos compartidos se leen en un repositorio y se comparan por hash/diff con el otro; no cargar dos copias idénticas al contexto.

## Alcance seguro

- Mantener los siete módulos M01–M07 y las decisiones aprobadas. Distinguir siempre heredado, propuesto y pendiente.
- Durante ETAPA 07: configurar stack, proyectos, entorno Docker/PostgreSQL, SQLAlchemy Async y migraciones iniciales **solo desde el diseño aprobado de ETAPA 06**. Dar prioridad al backend; preparar Flutter sin desarrollar funcionalidades. No inventar permisos/estados de negocio pendientes ni implementar los 40 RF (ETAPA 08). No marcar pruebas o migraciones como ejecutadas sin evidencia.
- Hacer cambios mínimos dentro de la etapa. No sobrescribir trabajo ajeno, registrar secretos, ejecutar commits/push/merge ni usar conectores externos sin necesidad.
- Mantener idénticos `docs/` compartidos entre backend y frontend. Las Skills específicas viven solo en su repositorio; ambos agentes usan el mismo `SKILL.md`.
- Usar archivos y Git locales primero. GitHub se reserva para operaciones remotas solicitadas; Figma para ETAPA 09; otros MCP requieren una necesidad vigente.

## Verificación y cierre

- Confirmar repositorio y rama `develop`, revisar cambios existentes y validar enlaces, trazabilidad y diferencias entre repositorios.
- Reportar archivos modificados, comprobaciones reales, riesgos y pendientes. No presentar inspección documental como prueba de ejecución.
- La aprobación de una etapa corresponde exclusivamente al usuario.

Procedimiento operativo ampliado: `docs/agentes/README.md`.
