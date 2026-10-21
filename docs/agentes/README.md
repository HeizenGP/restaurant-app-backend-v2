# Guía operativa de agentes — Restaurant App V2

**Aplica a ambos repositorios en `develop`.** `AGENTS.md` conserva reglas siempre activas; esta guía contiene el procedimiento compartido. No copiarla en prompts ni Skills.

## Selección de contexto

| Tipo de tarea | Leer | Añadir solo si hace falta |
|---|---|---|
| Cualquier tarea | `AGENTS.md`, índice y etapa vigente | Nada más por defecto. |
| Arquitectura/revisión transversal | Secciones afectadas de `etapa-05.md` | RF/RN/RNF concretos; casos de uso de ETAPA 04 aprobados documentalmente, con observaciones técnicas pendientes. |
| Slice FastAPI | Skill `restaurant-fastapi-slice` y sección backend de ETAPA 05 | CA del módulo y flujo puntual. |
| Slice Flutter | Skill `restaurant-flutter-slice` y sección Flutter/REST de ETAPA 05 | CA del módulo y pantalla/flujo puntual. |
| Duda de negocio | ETAPA 03 primero | ETAPAS 01–02 solo si la duda no queda resuelta. |
| Sincronización | Archivo ya editado y su homólogo | Hash/diff; no cargar ambos textos completos. |

Mantener en `docs/` las decisiones duraderas; el historial de conversación no es fuente. Una solicitud debe indicar objetivo, etapa, restricciones y evidencia esperada. La salida debe limitarse a decisiones, archivos, verificaciones, riesgos y pendientes.

## Coordinación Codex / AGY

- Ambos usan `AGENTS.md` y descubren Skills locales desde `.agents/skills/`; no crear formatos o copias por herramienta.
- Dividir trabajo paralelo por archivos y objetivos no superpuestos. Antes de editar, comprobar rama y árbol de trabajo.
- Modificar el documento compartido en un repositorio, replicarlo de forma mecánica y verificar igualdad byte a byte. Los README raíz pueden diferir en encabezado y descripción específica de Backend/Frontend.
- Si una etapa o decisión sigue pendiente, conservar esa etiqueta aunque una solución técnica la contemple.
- No hacer commit, push, merge ni acciones remotas salvo solicitud explícita.

## Skills vigentes

| Repositorio | Skill | Propósito |
|---|---|---|
| Backend | `.agents/skills/restaurant-fastapi-slice/SKILL.md` | Caso de uso M01–M07 con hexagonal, Vertical Slicing, permisos, consistencia y simulaciones. |
| Frontend | `.agents/skills/restaurant-flutter-slice/SKILL.md` | Feature de `customer_app` o `staff_app`, estado, navegación, REST y permisos. |

Las Skills enlazan `etapa-05.md`; no duplican matrices, estructura completa ni requisitos. Añadir otra Skill solo si existe un procedimiento repetido, especializado y no cubierto por estas reglas.

## Uso de MCP

1. Leer y editar repositorios con herramientas locales.
2. Usar GitHub solo para PR, issue u operación remota solicitada; no para releer archivos locales.
3. Usar Figma cuando ETAPA 09 o una tarea visual aprobada lo requiera.
4. Conectar otro servicio solo con una necesidad funcional vigente y permisos mínimos.
5. No cargar servidores, esquemas o manuales “por si acaso”; documentar una prueba MCP únicamente si se ejecutó.

## Protocolo de validación

1. Confirmar ambos repositorios en `develop` y revisar cambios previos.
2. Validar estructura de Skills (frontmatter `name`/`description`, coincidencia nombre/carpeta, restricciones de activación y referencias); ejecutar `quick_validate.py` si está disponible. Distinguir validación estática de prueba real de invocación en Codex/Antigravity.
3. Comprobar que los 40 RF siguen asignados una vez a M01–M07 y que ningún pendiente se presenta como aprobado.
4. Comparar archivos compartidos de `docs/` y reglas comunes entre repositorios.
5. Registrar herramientas no disponibles (por ejemplo, render PlantUML) como pendientes; no simular el resultado.
6. Dejar la etapa en revisión hasta la aprobación expresa del usuario.
