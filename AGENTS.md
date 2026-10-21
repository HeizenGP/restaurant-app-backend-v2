# Restaurant App V2 — Reglas para Codex y AGY

## Estado y autoridad

- **ETAPAS 00–03 aprobadas (2026-10-13) y ETAPA 04 aprobada expresamente por el usuario (2026-10-20), con comprobaciones técnicas pendientes. ETAPA 05 aprobada expresamente (2026-10-20). ETAPA 06 aprobada expresamente como diseño documental (2026-10-21), con decisiones de negocio abiertas. ETAPA 07 APROBADA expresamente por el usuario (2026-10-21); ETAPA 08 EN DESARROLLO: 08.00 y 08.01 verificados técnicamente, 08.02 pendiente.** La ETAPA 08 completa no está aprobada; no aprobar etapas por inferencia.
- Índice oficial: `docs/etapas/README.md`. Trabajo actual: `docs/etapas/etapa-08.md`; continuidad: `docs/etapas/etapa-08-progreso.md`.
- Las ETAPAS 01–03 prevalecen como línea base de negocio y requisitos. ETAPA 04 es línea base documental de casos de uso aprobada, pero no resuelve por sí sola RN-20/RN-21, RNF-08, responsables de M07 ni comprobantes.

## Carga selectiva

1. Leer este archivo, el índice y el documento de la etapa vigente.
2. Abrir solo los RF/RN/RNF y diagramas que afecten la tarea; no releer etapas completas si una referencia puntual basta.
3. **Skills técnicas bajo demanda:** activar `restaurant-fastapi-slice` solo para diseñar/revisar un caso de uso del backend (implementación desde ETAPA 08), y `restaurant-flutter-slice` solo para una funcionalidad Flutter (implementación desde ETAPA 10). Durante ETAPA 06, diseñar la BD sin activar Skills de implementación; en ETAPA 07, configurar herramientas sin adelantar funcionalidades. Cada Skill vive en `.agents/skills/<nombre>/SKILL.md` de su respectivo repositorio. No cargar ambas salvo revisión transversal.
4. Los documentos compartidos se leen en un repositorio y se comparan por hash/diff con el otro; no cargar dos copias idénticas al contexto.

## Alcance seguro

- Mantener los siete módulos M01–M07 y las decisiones aprobadas. Distinguir siempre heredado, propuesto y pendiente.
- **ETAPA 07 APROBADA:** su infraestructura es la línea base; no reconstruirla. **ETAPA 08: desarrollar exclusivamente backend** (M01–M07, 40 RF/48 CA) por bloques del plan oficial, sin tocar Flutter, Figma ni el repositorio frontend. No inventar permisos ni decisiones pendientes; pruebas ejecutadas solo con evidencia.
- Hacer cambios mínimos dentro de la etapa. No sobrescribir trabajo ajeno, registrar secretos, ejecutar commits/push/merge ni usar conectores externos sin necesidad.
- **Excepción explícita de ETAPA 08:** editar únicamente `restaurant-app-backend-v2`, incluida su documentación `docs/` y este `AGENTS.md`; no editar ni sincronizar el frontend en esta etapa. La sincronización general de documentos compartidos se retoma en otra etapa con autorización. Activar solo `.agents/skills/restaurant-fastapi-slice/SKILL.md` cuando corresponda.
- **Workspace único para Codex y AGY:** `/home/heizen27/proyectos/restaurant-app-v2/restaurant-app-backend-v2` (`~/proyectos/restaurant-app-v2/restaurant-app-backend-v2`), rama `develop`. Ambos comparten los mismos archivos locales, alternan el turno (un solo escritor activo) y registran el traspaso en `docs/etapas/etapa-08-progreso.md`; nunca asumir que se han publicado cambios locales. Usar Git local primero; GitHub solo por solicitud explícita. Figma queda para ETAPA 09.

## Verificación y cierre

- En ETAPA 08 confirmar el único workspace backend y rama `develop`, ejecutar `git status` antes de editar, revisar cambios locales y el bloque activo. No comprobar ni modificar el frontend salvo instrucción nueva.
- Reportar archivos modificados, comprobaciones reales, riesgos y pendientes. No presentar inspección documental como prueba de ejecución.
- La aprobación de una etapa corresponde exclusivamente al usuario.

Procedimiento operativo ampliado: `docs/agentes/README.md`.
