# ETAPA 03 — Ingeniería de requisitos

**Proyecto:** Restaurant App V2 — Chifa ASIA.  
**Estado:** APROBADA POR EL USUARIO COMO ESPECIFICACIÓN DOCUMENTAL (2026-10-13).  
**Criterio de organización:** los **siete módulos funcionales M01–M07** son la fuente principal para redactar requisitos; la ETAPA 01 y FL-01 se usan **únicamente para validar coherencia**, no para reorganizar el catálogo por pasos del flujo.

## 1. Catálogo modular

Para cada RF se ofrece un identificador estable, comportamiento, prioridad **aprobada para la línea base documental** y criterio de aceptación **Dado–Cuando–Entonces**. Los criterios de excepción se agregan solo donde afectan el funcionamiento principal. Prioridad M = Must Have y S = Should Have; las prioridades quedaron aprobadas como línea base académica el 2026-10-13.

### M01 — Usuarios y accesos

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M01-01** | El sistema debe permitir registro e inicio de sesión de clientes. | M | **CA-M01-01-01:** Dado un cliente con datos válidos, cuando se registra e inicia sesión, entonces accede a su cuenta.<br>**CA-M01-01-02:** Dadas credenciales incorrectas, cuando se intenta entrar, entonces se rechaza el acceso. |
| **RF-M01-02** | El sistema debe permitir continuar como invitado sin crear una cuenta. | M | **CA-M01-02-01:** Dado un visitante, cuando elige Invitado, entonces puede iniciar un pedido sin registro. |
| **RF-M01-03** | El sistema debe distinguir los seis actores y habilitar las acciones que corresponden a cada rol. | M | **CA-M01-03-01:** Dado un usuario Mozo, cuando ingresa, entonces puede operar las funciones autorizadas a Mozos. |
| **RF-M01-04** | El sistema debe permitir asignar varios roles a un mismo usuario y acumular los permisos. | M | **CA-M01-04-01:** Dado un usuario con roles Administrador y Cajero, cuando ingresa, entonces accede a las funciones permitidas por ambos. |
| **RF-M01-05** | El sistema debe otorgar acceso completo al Super Administrador y bloquear operaciones que exceden los roles del resto. | M | **CA-M01-05-01:** Dado el Super Administrador, cuando accede a cualquier módulo, entonces tiene permisos completos.<br>**CA-M01-05-02:** Dado un Cajero sin otros roles, cuando intenta aprobar un pedido, entonces se rechaza la acción. |

### M02 — Catálogo de productos

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M02-01** | El sistema debe mostrar catálogo de productos organizado por categorías, con precio y disponibilidad. | M | **CA-M02-01-01:** Dado un producto publicado, cuando el cliente abre su categoría, entonces visualiza nombre, precio y disponibilidad. |
| **RF-M02-02** | El sistema debe permitir al Administrador crear y editar categorías, productos y precios. | M | **CA-M02-02-01:** Dado un Administrador, cuando guarda un producto válido, entonces el catálogo muestra sus datos actualizados. |
| **RF-M02-03** | El sistema debe permitir al Administrador modificar manualmente la cantidad de stock de cada producto. | M | **CA-M02-03-01:** Dado un producto con stock 8, cuando el Administrador establece 12, entonces queda stock 12. |
| **RF-M02-04** | El sistema debe permitir al Administrador habilitar o deshabilitar manualmente la venta de un producto. | M | **CA-M02-04-01:** Dado un producto con stock, cuando el Administrador lo deshabilita, entonces no puede incorporarse a un nuevo pedido. |
| **RF-M02-05** | El sistema debe comprobar que todos los productos estén habilitados y tengan stock suficiente antes de confirmar un pedido. | M | **CA-M02-05-01:** Dado un producto con 2 unidades, cuando se intenta confirmar una solicitud de 3, entonces se impide la confirmación. |
| **RF-M02-06** | El sistema debe descontar del stock las cantidades de los productos una sola vez al confirmar el pedido. | M | **CA-M02-06-01:** Dado un producto con 10 unidades, cuando se confirma un pedido de 2, entonces el stock queda en 8.<br>**CA-M02-06-02:** Dada una solicitud pendiente, cuando se consulta stock, entonces no se ha descontado por esa solicitud. |

### M03 — Gestión de mesas

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M03-01** | El sistema debe permitir al Administrador registrar y actualizar mesas y su distribución en el único restaurante. | M | **CA-M03-01-01:** Dado un Administrador, cuando registra una mesa, entonces se presenta en la distribución del local. |
| **RF-M03-02** | El sistema debe mostrar las mesas del restaurante al cliente que seleccione consumo en local desde la app. | M | **CA-M03-02-01:** Dado un cliente en consumo en local, cuando entra a la selección de mesa, entonces visualiza las mesas registradas. |
| **RF-M03-03** | El sistema debe asociar cada pedido de consumo en local a la mesa indicada por el Mozo o elegida desde la app. | M | **CA-M03-03-01:** Dado un pedido presencial, cuando queda registrado, entonces conserva la mesa asociada. |
| **RF-M03-04** | El sistema debe permitir consultar y actualizar la ocupación de las mesas al personal autorizado. | S | **CA-M03-04-01:** Dado un Mozo o Administrador, cuando consulta una mesa, entonces observa su ocupación y puede actualizarla. |

### M04 — Gestión de pedidos

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M04-01** | El sistema debe permitir seleccionar consumo en local, recojo en local o delivery como modalidad del pedido. | M | **CA-M04-01-01:** Dado un cliente en la app, cuando inicia un pedido, entonces puede elegir una de las tres modalidades. |
| **RF-M04-02** | El sistema debe permitir al cliente seleccionar productos y cantidades y enviar su solicitud desde la app. | M | **CA-M04-02-01:** Dado un carrito con productos, cuando el cliente envía el pedido, entonces se registra pendiente de revisión. |
| **RF-M04-03** | El sistema debe permitir al Mozo registrar pedidos presenciales asociados a mesa sin una segunda aprobación. | M | **CA-M04-03-01:** Dado un Mozo y una mesa, cuando registra un pedido con stock suficiente, entonces puede confirmarlo directamente. |
| **RF-M04-04** | El sistema debe permitir al Administrador registrar pedidos recibidos por llamada o WhatsApp e identificar el canal. | M | **CA-M04-04-01:** Dado un pedido por WhatsApp, cuando lo registra el Administrador, entonces figura con ese canal y su modalidad. |
| **RF-M04-05** | El sistema debe registrar modalidad, canal, cantidades, precios, total y mesa o información de entrega que corresponda. | M | **CA-M04-05-01:** Dado un pedido delivery, cuando se registra, entonces muestra productos, total y dirección, sin exigir mesa. |
| **RF-M04-06** | El sistema debe permitir a Mozo o Administrador aprobar o rechazar solicitudes de consumo en local enviadas desde la app después de verificar la mesa. | M | **CA-M04-06-01:** Dada una solicitud con mesa verificada, cuando Mozo o Administrador aprueba, entonces puede continuar a confirmación.<br>**CA-M04-06-02:** Dado un Cajero sin otro rol, cuando intenta aprobar, entonces se deniega. |
| **RF-M04-07** | El sistema debe permitir solo al Administrador aprobar o rechazar las solicitudes de recojo y delivery enviadas desde la app. | M | **CA-M04-07-01:** Dada una solicitud de delivery, cuando el Administrador la aprueba, entonces puede continuar a verificación del anticipo.<br>**CA-M04-07-02:** Dado un Mozo sin rol de Administrador, cuando intenta aprobar delivery, entonces se deniega. |
| **RF-M04-08** | El sistema debe impedir confirmación y preparación de solicitudes rechazadas e informar su estado al cliente. | M | **CA-M04-08-01:** Dada una solicitud rechazada, cuando el cliente consulta, entonces visualiza el rechazo y no se genera comanda. |
| **RF-M04-09** | El sistema debe confirmar pedidos únicamente después de las verificaciones de autorización, stock y anticipo aplicables. | M | **CA-M04-09-01:** Dado un pedido presencial con stock suficiente, cuando se confirma, entonces puede enviarse a cocina sin anticipo.<br>**CA-M04-09-02:** Dado un delivery sin anticipo confirmado, cuando se intenta confirmar, entonces la acción se bloquea. |
| **RF-M04-10** | El sistema debe permitir consultar el estado del pedido desde su solicitud hasta su cierre. | M | **CA-M04-10-01:** Dado un pedido marcado Listo por cocina, cuando se consulta, entonces se muestra el estado actualizado. |
| **RF-M04-11** | El sistema debe calcular el importe total del pedido a partir de precios y cantidades. | M | **CA-M04-11-01:** Dadas dos unidades de un producto de S/ 12, cuando se calcula el importe de esas unidades, entonces es S/ 24. |

### M05 — Cocina y comandas

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M05-01** | El sistema debe enviar a cocina una comanda solo cuando el pedido esté confirmado. | M | **CA-M05-01-01:** Dado un pedido confirmado, cuando se envía a preparación, entonces cocina recibe su comanda.<br>**CA-M05-01-02:** Dado un pedido pendiente, cuando cocina consulta comandas, entonces no se ofrece para preparar. |
| **RF-M05-02** | El sistema debe mostrar al personal de cocina el contenido y cantidades de cada comanda habilitada. | M | **CA-M05-02-01:** Dada una comanda con tres productos, cuando cocina la abre, entonces ve productos y cantidades. |
| **RF-M05-03** | El sistema debe permitir al personal de cocina establecer el estado En preparación. | M | **CA-M05-03-01:** Dada una comanda recibida, cuando cocina inicia su trabajo, entonces el pedido cambia a En preparación. |
| **RF-M05-04** | El sistema debe permitir a cocina establecer el estado Listo tras finalizar la preparación de todos los productos. | M | **CA-M05-04-01:** Dado un pedido completamente preparado, cuando cocina marca Listo, entonces se habilita su atención o entrega. |

### M06 — Caja y pagos

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M06-01** | El sistema debe permitir al Cajero registrar cobros relacionados con un pedido y actualizar el saldo. | M | **CA-M06-01-01:** Dado un pedido con saldo pendiente, cuando el Cajero registra un cobro válido, entonces queda anotado y se recalcula el saldo. |
| **RF-M06-02** | El sistema debe calcular el anticipo obligatorio del 50 % del total de cada pedido para recojo o delivery. | M | **CA-M06-02-01:** Dado un pedido de recojo de S/ 80, cuando se calcula el anticipo, entonces se requieren S/ 40. |
| **RF-M06-03** | El sistema debe permitir que el Administrador verifique y registre anticipos de recojo/delivery sin habilitarle por ello el acceso general a Caja. | M | **CA-M06-03-01:** Dado un pedido de delivery con anticipo verificado, cuando el Administrador registra la verificación, entonces se habilita el paso de confirmación. |
| **RF-M06-04** | El sistema debe bloquear el envío de comandas de recojo/delivery mientras el anticipo no esté confirmado. | M | **CA-M06-04-01:** Dado un pedido de recojo sin anticipo confirmado, cuando se intenta enviar a cocina, entonces la comanda no se emite. |
| **RF-M06-05** | El sistema debe registrar el cobro del 50 % restante al entregar recojo o delivery y mostrar saldo pendiente. | M | **CA-M06-05-01:** Dado un pedido de S/ 100 con anticipo de S/ 50, cuando Caja registra otros S/ 50, entonces el saldo queda en cero. |
| **RF-M06-06** | El sistema debe mostrar estado de pago y bloquear el cierre si hay saldo pendiente. | M | **CA-M06-06-01:** Dado un pedido con saldo pendiente de S/ 20, cuando se intenta cerrar, entonces se informa el saldo y se bloquea el cierre. |

### M07 — Atención y cierre de entregas

| ID | Requisito funcional propuesto | MoSCoW | Criterios de aceptación |
|---|---|:---:|---|
| **RF-M07-01** | El sistema debe registrar que un pedido de consumo en local fue servido en su mesa. | M | **CA-M07-01-01:** Dado un pedido en local Listo, cuando el Mozo confirma que lo sirvió, entonces queda registrado como servido. |
| **RF-M07-02** | El sistema debe registrar que un pedido de recojo fue entregado en el restaurante. | M | **CA-M07-02-01:** Dado un pedido para recojo Listo, cuando se registra su entrega, entonces queda constancia del recojo. |
| **RF-M07-03** | El sistema debe registrar la entrega de un pedido de delivery sin gestionar repartidores ni rutas. | M | **CA-M07-03-01:** Dado un pedido delivery Listo, cuando se informa que fue entregado, entonces se registra el evento sin datos de transporte. |
| **RF-M07-04** | El sistema debe cerrar un pedido solo si se registraron su atención o entrega y el pago total. | M | **CA-M07-04-01:** Dado un pedido servido o entregado y sin saldo pendiente, cuando se cierra, entonces pasa a Cerrado.<br>**CA-M07-04-02:** Dado un pedido no entregado, cuando se intenta cerrar, entonces se rechaza. |

## 2. Convenciones y criterios de revisión

- Cada RF pertenece a **un módulo** y puede relacionarse con otros. Los permisos definidos prevalecen sobre cualquier pantalla o interfaz.
- Los RF y CA son una **especificación documental aprobada por el usuario (2026-10-13)**; no constituyen funcionalidades implementadas ni pruebas de software ejecutadas.
- No se incorporan integración automática de WhatsApp, logística de repartidores, inventario de ingredientes, sedes, reservas ni facturación electrónica.
- Las aprobaciones por modalidad, el descuento de stock y el anticipo son comprobaciones indispensables.
- Para simulaciones académicas, verificar manualmente el anticipo no equivale a integración con bancos ni pasarelas de pago.

**Trazabilidad:** [Resumen, RNF, RN y decisiones](etapa-03.md).
