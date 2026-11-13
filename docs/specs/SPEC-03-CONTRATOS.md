# SPEC-03 — Contratos de módulos, API y autorización

## Contrato interno estándar
Los servicios de aplicación aceptan DTOs validados y `ActorContext { actorId, role, storeId?, courierId? }`, retornan DTOs sin objetos DynamoDB/Redis. Errores de dominio tipados: ValidationError, NotFoundError, ForbiddenError, ConflictError, DependencyUnavailableError. Se prohíbe importar infraestructura privada entre módulos.

## Interfaces mínimas
- Identity: `require_actor`, `authorize`.
- Stores: `get_store`, `assert_store_enabled`, `build_store_condition`.
- Couriers: `get_courier`, `assert_eligible`, `build_courier_condition`.
- Orders: `create_order`, `get_order`, `list_store_orders`, `build_order_transition`.
- Dispatch: `accept_order`, `mark_picked_up`, `mark_delivered`, `cancel_order`.
- Availability: `set_availability`, `heartbeat`, `list_present_couriers`.
- Tracking: `get_tracking(token)`.
- Analytics: `get_store_month_stats`.

## API pública v1
`POST /api/v1/stores`; `POST /api/v1/couriers`; `PATCH /api/v1/couriers/me/availability`; `POST /api/v1/couriers/me/heartbeat`; `POST /api/v1/orders`; `GET /api/v1/orders/{id}`; `GET /api/v1/stores/me/orders`; `GET /api/v1/orders/available?zoneId=...`; `POST /api/v1/orders/{id}/accept`; `POST /api/v1/orders/{id}/pickup`; `POST /api/v1/orders/{id}/deliver`; `POST /api/v1/orders/{id}/cancel`; `GET /api/v1/couriers/me/orders`; `GET /api/v1/tracking/{token}`; `GET /api/v1/stores/me/stats?month=YYYY-MM`.

## Contrato de errores
`{ "error": { "code": "ORDER_ALREADY_ASSIGNED", "message": "Entrega ya asignada", "requestId": "..." } }`. Códigos HTTP: 400, 401, 403, 404, 409, 429, 500, 503. Paginación `limit` y `nextCursor` opaco.

## Seguridad
El actor se obtiene de contexto autenticado. Autenticación local de desarrollo debe ser explícita y aislada; nunca promover un header de rol sin verificación a producción. Tracking devuelve solo estado, hitos y tiempos, sin exponer información sensible.

## Aceptación
OpenAPI validado; DTOs y errores tipados; pruebas de contrato de cada endpoint; pruebas 401/403 y aislamiento por comercio. El `contratos/openapi.yaml` heredado es borrador: actualizarlo para coincidir con estas rutas antes de implementar handlers.
