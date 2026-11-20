# SPEC-02 — Transacciones, estados e idempotencia

**Estado:** implementada; evidencias en [validación](../validation.md).

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

## Implementación

| Comando | Función | Acciones en el commit |
| --- | --- | --- |
| T1 crear | `orders.service.create_order` | ConditionCheck comercio habilitado+versión, Put META, Put CREATED, Put vista de estado, Put idempotencia |
| T2 aceptar | `dispatch.service.accept_order` | Put META (versión), Put evento, Put vista comercio (versión), ConditionCheck repartidor habilitado/disponible/zona/versión, Put ACTIVE (ausencia), Put vista courier, Put idempotencia |
| T3 recoger | `dispatch.service.pick_up_order` | Put META, evento, vista comercio y vista courier (versión), idempotencia |
| T4 entregar | `dispatch.service.deliver_order` | T3 + Delete ACTIVE condicionado al orderId + Update STATS con `ADD` |
| T5 cancelar | `dispatch.service.cancel_order` | META, evento, vista comercio; si estaba asignado, vista courier y Delete ACTIVE |
| FAILED | `dispatch.service.fail_order` | Solo ADMIN, desde PICKED_UP; libera ACTIVE |

- `shared/storage/transactions.run_command`: huella canónica del payload, consulta del registro previo, commit con el registro idempotente, traducción de `CancellationReasons` a errores de dominio y reintento ante `TransactionConflict`.
- `shared/exceptions`: `ValidationError` 400, `UnauthorizedError` 401, `ForbiddenError` 403, `NotFoundError` 404, `ConflictError` 409, `DependencyUnavailableError` 503.
- `identity/contracts.ActorContext`: actor verificado; en el MVP el ID del comercio o repartidor coincide con el del usuario, por lo que la pertenencia la fija el servidor.
- `analytics/repository.build_increment`: contador atómico; `analytics/service`: Cache-Aside con invalidación poscommit.
- `tracking/tokens.issue_token`: secreto derivado por HMAC; DynamoDB guarda solo su SHA-256.

## Evidencia
- `app/tests/test_commands.py`: ciclo completo, idempotencia y conflicto de huella, 100 repartidores (secuencial), dos pedidos para un repartidor, carrera perdida en el commit sin escrituras parciales, cancelaciones, visibilidad, FAILED, elegibilidad y Redis caído.
- `app/tests/integration/test_concurrency.py`: 100 hilos contra MiniStack con un único ganador y un repartidor contra dos pedidos.

## Límites
La retención de registros idempotentes sigue sin TTL. Las rutas HTTP, la autenticación y los DTO públicos corresponden a SPEC-03/04/05.
