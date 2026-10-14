# Guía operativa de agentes — Restaurant App V2

**Aplica a ambos repositorios, rama `develop`.** Codex y AGY comparten `AGENTS.md`; no es necesario crear reglas duplicadas para cada herramienta. Esta guía es contextual y se consulta cuando la tarea lo requiera.

## 00.1 — Ahorro de tokens y gestión del contexto

1. **Entrada mínima:** leer `AGENTS.md`, el índice `docs/etapas/README.md` y el archivo de la etapa vigente. Consultar otras fuentes solo si son relevantes.
2. **Lectura puntual:** priorizar rutas y fragmentos específicos; evitar cargar repositorios completos, repetir archivos ya conocidos o buscar en dependencias generadas.
3. **Tareas delimitadas:** una solicitud debe especificar objetivo, alcance, restricciones y evidencia de verificación. Dividir trabajos extensos sin cambiar etapas por cuenta propia.
4. **Salida compacta:** informar solo decisiones, archivos tocados, verificaciones reales, riesgos y pendientes. Omitir logs largos salvo error relevante.
5. **Contexto persistente:** conservar las decisiones aprobadas en `docs/`; no depender del historial de conversación ni mantener un diario redundante.
6. **Un solo origen de instrucciones:** `AGENTS.md` para reglas siempre activas; documentos específicos para detalle. Evitar copiar el contenido de las guías en cada prompt.

## 00.2 — Coordinación Codex / AGY

- Ambos obedecen el mismo `AGENTS.md` de su repositorio.
- Si trabajan en paralelo, dividir **archivos y objetivos no superpuestos**. No editar una misma ruta simultáneamente.
- Antes de transferir trabajo, registrar en el documento de etapa el estado, los acuerdos confirmados, cambios y pendientes esenciales.
- Comparar la documentación compartida en ambos repositorios después de modificarla. Cada agente debe revisar diferencias y respetar cambios externos.
- La aprobación de cada etapa corresponde al usuario, una vez comprobados sus criterios.

## 00.3 — Skills, documentación modular y MCP

**Skills:** en ETAPA 00 no crear Skills específicas de Flutter, FastAPI, BD o arquitectura. En ETAPA 05, cuando se apruebe la arquitectura, evaluar Skills concretas con propósito, desencadenante y referencias breves; instalar solo las necesarias.

**Documentación:** `docs/etapas/README.md` es el índice; `docs/etapas/etapa-XX.md` describe el alcance, decisiones y aceptación de su etapa. Las reglas persistentes van en `AGENTS.md`; la operativa de agentes en esta guía. No crear carpetas ni documentos sin utilidad actual.

**MCP:** conectar herramientas por demanda y por permisos mínimos. GitHub se utiliza para repositorios cuando esté habilitado; Figma se evalúa en ETAPA 09. Otros MCP requieren necesidad demostrada. No incorporar secretos ni suponer que un conector está configurado en la instalación local; comprobarlo cuando se use.

## Protocolo de validación

1. Verificar que ambos repositorios usan `develop`.
2. Comprobar que `AGENTS.md`, esta guía y el documento de la etapa vigente existen y son coherentes.
3. Verificar que los archivos compartidos en `docs/` tengan el mismo contenido.
4. Probar **por separado** que Codex y AGY interpretan la etapa y sus prohibiciones en cada workspace, sin pedirles crear código.
5. Confirmar localmente los MCP solo cuando sean necesarios. Anotar cualquier prueba no ejecutada como pendiente.

**No equivale a validación de ejecución:** revisar archivos en GitHub no demuestra que los agentes locales o sus MCP estén operativos.
