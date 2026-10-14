# ETAPA 01 — Análisis del negocio y alcance

**Estado: EN DEFINICIÓN / NO APROBADA.** La ETAPA 00 está aprobada.

## Objetivo
Definir desde cero cómo funciona Chifa ASIA, qué problemas resolverá el sistema, sus actores, modalidades de consumo y funcionalidades incluidas, simuladas o excluidas. Priorizar el flujo principal, sin detallar cuestiones secundarias que no sean necesarias.

## Decisiones confirmadas
- **Negocio:** un solo restaurante, sin sedes.
- **Actores:** cliente, mozo, cajero, administrador y superadministrador (acceso completo).
- **App de cliente:** inicio de sesión, registro o acceso como invitado; elección de consumo en local, recojo en local o delivery.
- **Consumo en local:** el mozo puede atender y registrar el pedido de la mesa para enviarlo a cocina; alternativamente, el cliente selecciona la mesa y realiza su pedido desde la app. El pedido de la app requiere revisión presencial de la mesa y aprobación del personal autorizado antes de cocina.
- **Recojo y delivery:** pedidos por app, llamada o WhatsApp. El administrador registra los recibidos por llamada o WhatsApp; los de la app pasan por revisión/aprobación autorizada.
- **Anticipo:** para recojo y delivery debe confirmarse el pago del **50 %** antes de enviar la comanda a cocina.
- **Cancelaciones:** la eventual devolución del anticipo queda a criterio del administrador; no ampliar el sistema con procedimientos de reembolso no solicitados.

## Pendiente de definir en esta etapa
- Problemática y objetivos concretos del restaurante.
- Responsabilidades y permisos esenciales por actor.
- Funcionamiento general de los tres servicios hasta la entrega y el cobro.
- Funcionalidades **incluidas, simuladas y excluidas**, sin añadir módulos no solicitados.

## Límite de la etapa
Solo análisis y decisiones del negocio. El **diagrama de flujo principal con rombos y sus subflujos** se diseña en ETAPA 02. Los requisitos son de ETAPA 03, UML de ETAPA 04 y arquitectura de ETAPA 05.

**No retomar decisiones del proyecto anterior.** No avanzar a ETAPA 02 ni marcar la ETAPA 01 como aprobada sin validación del usuario. Documentar y sincronizar acuerdos en `docs/` de backend y frontend.
