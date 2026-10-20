---
name: restaurant-fastapi-slice
description: Diseña, implementa o revisa un caso de uso FastAPI de Restaurant App V2 dentro de M01–M07, con arquitectura hexagonal, Vertical Slicing, permisos y trazabilidad. No usar para trabajo exclusivamente Flutter o para cambiar requisitos de negocio.
---

# Slice FastAPI de Restaurant App V2

## Contexto mínimo

Lee `AGENTS.md`, `docs/etapas/README.md` y las secciones pertinentes de `docs/etapas/etapa-05.md`. Consulta solo los RF/RN/RNF del módulo afectado en ETAPA 03. Usa los CU de ETAPA 04, aprobados como documentación, solo cuando sean pertinentes; conserva sus observaciones técnicas y permisos aún pendientes.

## Procedimiento

1. Identifica un módulo propietario, RF/CA, actor, permiso y estado previo/posterior. Si una decisión está pendiente, no la conviertas en comportamiento.
2. Mantén el slice en `modules/mXX_nombre/application/use_cases/verbo_objeto`; dominio sin FastAPI, Pydantic u ORM, y adaptadores en el borde.
3. Define los puertos que el caso de uso consume. Comunica módulos mediante contratos públicos en proceso; no importes adaptadores, repositorios ni dominio ajeno.
4. Comprueba autorización en el handler además del adaptador HTTP. Trata al Invitado como sesión limitada, roles como unión de permisos y Super Administrador como acceso total.
5. Para confirmar, cobrar, verificar anticipo, atender/entregar o cerrar, conserva idempotencia, control de concurrencia y auditoría. En ConfirmOrder usa la UoW única compartida entre M04/M02/M05; la confirmación consulta el anticipo ya registrado por M06, sin crear un nuevo abono. Mantén separados el permiso administrativo de verificar anticipo y el permiso de Caja.
6. Simula solo mediante adaptadores explícitos. Llamada/WhatsApp son canales manuales; no añadas pagos reales, mapas, delivery logístico o SUNAT.
7. Verifica reglas de dominio con pruebas del handler y puertos falsos; usa integración para adaptadores/contrato. Reporta trazas RF/RN/RNF, archivos y pruebas reales.

No instales dependencias ni inicialices FastAPI si la etapa vigente no lo autoriza.
