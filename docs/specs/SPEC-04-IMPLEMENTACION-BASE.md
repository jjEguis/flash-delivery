# SPEC-04 — Primer incremento vertical

**Estado:** implementada; evidencias en [validación](../validation.md).

## Alcance
Implementar Identity local de desarrollo, Stores, Couriers y Orders (crear/consultar/listar), sin Dispatch todavía.

## Orden
1. Contratos DTO y ActorContext.
2. Stores: registro, habilitación, consulta.
3. Couriers: registro, zona, habilitación y disponibilidad declarada.
4. Orders: creación transaccional, consulta y listado con GSI1/GSI2.
5. Pruebas de integración, autorización y paginación.

## Aceptación
Un comercio habilitado crea pedido; aparece en lista del comercio y en abiertos de su zona; comercio ajeno no puede consultarlo con privilegios de propietario; evento CREATED y vista de estado existen; requestId repetido no duplica pedido.

## Implementación

| Módulo | Servicio | Handler (Lambda `flashdelivery-<módulo>`) |
| --- | --- | --- |
| Stores | `stores/service.py`: catálogo de zonas (`ZONES`), alta propia deshabilitada, consulta, habilitación ADMIN con versión | `GET /zones`, `POST /stores`, `GET /stores/me`, `PATCH /admin/stores/{storeId}` |
| Couriers | `couriers/service.py`: alta propia, disponibilidad declarada (T6), habilitación ADMIN (deshabilitar también quita la disponibilidad), pedido activo, historial | `POST /couriers`, `GET /couriers/me`, `PATCH /couriers/me/availability`, `GET /couriers/me/active`, `GET /couriers/me/orders`, `PATCH /admin/couriers/{courierId}` |
| Orders | `orders/service.py`: crear (T1), detalle con visibilidad, eventos, listados AP05/AP06/AP08 | `POST /orders`, `GET /orders/available`, `GET /orders/{orderId}`, `GET /orders/{orderId}/events`, `GET /stores/me/orders` |

- El stack CDK crea una Lambda por módulo implementado a partir de `infra/routes.py`, todas desde el mismo ZIP empaquetado, con permisos de lectura/escritura sobre la tabla.
- Las altas de perfil quedan deshabilitadas hasta que un ADMIN las aprueba; los cambios de perfil usan `expected_version` (bloqueo optimista) mediante `transactions.commit`.
- Listados: `page_dto` traduce cursores manipulados o de otra consulta a 400. Los listados omiten la dirección de destino; el detalle solo lo ven el comercio propietario, el repartidor asignado y ADMIN. Para cualquier otro actor un pedido ajeno responde 404, sin revelar su existencia.
- `GET /orders/available` exige repartidor registrado, habilitado y de la zona consultada (o ADMIN).

## Evidencia
- `app/tests/test_http_base_flow.py`: endpoints con moto/fakeredis, roles, 401/403/404/409, zona inválida, idempotencia por HTTP, paginación con cursor, filtro por estado, cursor manipulado y aislamiento entre comercios.
- `app/tests/integration/test_api_flow.py`: el mismo flujo por API Gateway → Lambda empaquetada → DynamoDB en MiniStack, con espera de convergencia de GSI y limpieza por claves exactas.
