# ETAPA 00 — Configuración de agentes de IA

**Estado: APROBADA por el usuario el 2026-10-13.** Fecha de inicio: 2026-10-13.

## Objetivo
Preparar una forma compartida, documentada y de bajo consumo de contexto para que Codex y AGY colaboren en los repositorios backend y frontend antes de implementar el sistema.

## Alcance y entregables

### 00.1 — Estrategia de ahorro de tokens
- [x] Definir lectura progresiva del contexto, tareas acotadas y respuestas breves en `docs/agentes/README.md`.
- [x] Centralizar instrucciones siempre activas en `AGENTS.md`; evitar duplicación de reglas y carga masiva de archivos.

### 00.2 — Reglas compartidas mediante AGENTS.md
- [x] Alinear instrucciones, etapa vigente, límites de alcance, seguridad y coordinación en los dos repositorios.
- [x] Establecer `develop` como rama de trabajo y prohibir decisiones técnicas no aprobadas.

### 00.3 — Skills, documentación modular, MCP y contexto
- [x] Definir estructura documental mínima e instrucciones para el relevo de agentes.
- [x] Documentar uso de MCP por necesidad y permisos mínimos, sin registrar credenciales.
- [x] Reservar la creación/consolidación de Skills técnicas para ETAPA 05.

### 00.4 — Validación de configuración
- [x] Revisar desde GitHub la estructura inicial y la rama `develop` en ambos repositorios.
- [x] Confirmar después de los commits la existencia y consistencia de las guías en ambos repositorios.
- [x] Validación de la configuración de Codex en ambos repositorios: aprobada por el usuario (sin evidencia técnica local adjunta).
- [x] Validación de la configuración de AGY en ambos repositorios: aprobada por el usuario (sin evidencia técnica local adjunta).
- [x] Política MCP documentada; la prueba de cada conexión se efectuará cuando se necesite, no se declara realizada.

## Criterios para aprobar la ETAPA 00

1. Ambos agentes identifican correctamente la etapa vigente y respetan la prohibición de implementar funciones.
2. `AGENTS.md` y los documentos compartidos son coherentes y están sincronizados entre los dos repositorios.
3. El protocolo de ahorro de tokens y coordinación está escrito y es aplicable.
4. Se documentan los conectores disponibles o pendientes sin inventar instalaciones o resultados.
5. El usuario confirma el cierre de la etapa.

## Prohibiciones vigentes
No instalar dependencias o frameworks, no generar apps, no crear API ni base de datos, no adelantar arquitectura ni Skills específicas, y no asumir acuerdos anteriores.

## Evidencia y pendientes
- Evidencia documental: `AGENTS.md`, `docs/agentes/README.md`, este archivo y el plan maestro.
- Verificación GitHub: se completa al revisar los archivos publicados en ambos repositorios.
- El usuario aprueba la validación de ambos repositorios; no se adjuntaron registros locales de ejecución. La conexión real de MCP se comprobará según necesidad.
- **Siguiente: ETAPA 01 — POR INICIAR / NO APROBADA.**
