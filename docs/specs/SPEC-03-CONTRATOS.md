# SPEC-03 — Contratos de módulos, API y autorización

**Estado:** implementada; evidencias en [validación](../validation.md). Contrato HTTP en [`docs/api/openapi.json`](../api/openapi.json).

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
Las 27 operaciones están en `app/infra/routes.py` (registro único) y en el OpenAPI. Además de las rutas originales se añadieron: inicio de sesión de desarrollo, catálogo de zonas, perfil propio, habilitación administrativa, pedido activo, eventos del pedido, salida de presencia, presencia por zona y FAILED administrativo.

## Contrato de errores
`{ "error": { "code": "ORDER_ALREADY_ASSIGNED", "message": "Entrega ya asignada", "requestId": "..." } }`. Códigos HTTP: 400, 401, 403, 404, 409, 429, 500, 503. Paginación `limit` y `nextCursor` opaco.

## Seguridad
El actor se obtiene de contexto autenticado. Autenticación local de desarrollo debe ser explícita y aislada; nunca promover un header de rol sin verificación a producción. Tracking devuelve solo estado, hitos y tiempos, sin exponer información sensible.

## Aceptación
OpenAPI validado; DTOs y errores tipados; pruebas de contrato de cada endpoint; pruebas 401/403 y aislamiento por comercio.

## Implementación

- **Identidad local (ADR-007):** `identity/tokens.py` firma `payload.firma` con HMAC-SHA256 (`DEV_AUTH_SECRET`), con expiración de 12 h. `POST /api/v1/auth/dev-login` emite tokens STORE/COURIER para cualquier `userId` válido y ADMIN solo con `DEV_ADMIN_CODE`. Solo funciona con `ENVIRONMENT=local`, que `Settings` ya exige. No es apto para producción.
- **Pertenencia fijada por el servidor:** en el MVP cada usuario STORE/COURIER tiene un único perfil cuyo ID es su `actorId`; ningún endpoint acepta el ID del comercio o del repartidor desde el cuerpo.
- **Capa HTTP (`shared/http.py`):** enrutado por plantilla con parámetros (admite el prefijo de etapa en `rawPath`), lectura de JSON con límite de 16 KiB, `Idempotency-Key`, paginación, contrato de errores con `requestId`, ocultación de errores internos, logs estructurados sin tokens ni direcciones y límite de escrituras por actor y ruta en Redis (`ratelimit:<actor>:<ruta>:<minuto>`, 120/min por defecto; si Redis falla no bloquea).
- **Registro de rutas (`infra/routes.py`):** lo usan el stack CDK, el router de cada handler y las pruebas, de modo que API Gateway, código y OpenAPI no pueden desalinearse.

## Evidencia
`app/tests/test_api_contract.py`: OpenAPI ↔ registro ↔ handlers, resolución de `$ref`, operaciones públicas y con `Idempotency-Key`, firma/expiración/manipulación de tokens, dev-login y ADMIN, 401/404/400, error interno oculto y límite de solicitudes por actor con caída de Redis. Las pruebas por endpoint y de aislamiento entre comercios se agregan con cada handler en SPEC-04/05.
