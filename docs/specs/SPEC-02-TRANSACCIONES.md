# SPEC-02 — Transacciones, estados e idempotencia

## Estados
`PENDING -> ASSIGNED -> PICKED_UP -> DELIVERED`; `PENDING|ASSIGNED -> CANCELLED`; `PICKED_UP -> FAILED` solo con autorización excepcional.

## Comandos
- `CreateOrder(actor, payload, requestId)`: comprobar comercio habilitado; crear META, CREATED, vista de estado e idempotencia.
- `AcceptOrder(courier, orderId, requestId)`: comprobar perfil habilitado/disponible/zona; condicionar META en PENDING y courierId ausente; crear ACTIVE, evento, vista courier; cambiar vista de comercio; idempotencia. Todo en una transacción.
- `PickUpOrder(courier, orderId, requestId)`: condicionar ASSIGNED y courier asignado; actualizar META, evento y vista.
- `DeliverOrder(courier, orderId, requestId)`: condicionar PICKED_UP y courier asignado; actualizar META, evento y vista; borrar ACTIVE condicionado; agregar estadística exactamente una vez por comando confirmado.
- `CancelOrder(store, orderId, requestId)`: condicionar propiedad y estado elegible; actualizar META, evento y vista; liberar ACTIVE si existe.

## Invariantes y errores
- Como máximo un courier por pedido y un pedido activo por courier.
- Dos aceptaciones concurrentes: exactamente una confirma, demás 409.
- Repetición de requestId y mismo payload: mismo resultado sin segunda mutación.
- Reutilización de requestId con payload distinto: 409.
- Cambios no autorizados: 403; estado inválido: 409; inexistente: 404.
- Ninguna transacción incluye dos acciones sobre el mismo ítem.

## Pruebas
100 couriers compiten por un pedido; 1 courier compite por 2 pedidos; reintentos y timeout; cancelación contra aceptación; entrega contra cancelación; error condicional sin proyecciones parciales; Redis caído no produce doble asignación.

## Nota de diseño
Los constructores de operaciones de módulos son contratos internos, no repositorios ajenos. Si el límite de acciones transaccionales o la disponibilidad del emulador impide una operación, registrar bloqueo y rediseñar explícitamente.
