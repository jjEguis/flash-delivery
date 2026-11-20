# SPEC-05 — Dispatch, Availability, Tracking y Analytics

**Estado:** implementada; evidencias en [validación](../validation.md).

## Alcance
Implementar aceptación competitiva, transiciones, heartbeats Redis, seguimiento y estadísticas básicas.

## Orden
1. Dispatch aceptar + prueba concurrente.
2. Recoger, entregar y cancelar con transacciones.
3. Availability con heartbeat, ZSET, expiración y reconciliación.
4. Tracking por token limitado.
5. Analytics mensual con actualización idempotente y caché.

## Aceptación
Una aceptación exitosa entre 100 solicitudes; repartidor no acepta segundo pedido activo; historial consistente; Redis caído no permite asignación duplicada; seguimiento no filtra datos privados; estadísticas no se duplican con reintentos.

## Implementación

| Módulo | Endpoints | Notas |
| --- | --- | --- |
| Dispatch | `POST /orders/{orderId}/accept|pickup|deliver|cancel|fail` | Comandos de SPEC-02 con `Idempotency-Key`; la entrega invalida la caché de estadísticas después del commit |
| Availability | `POST|DELETE /couriers/me/heartbeat`, `GET /zones/{zoneId}/couriers` | El heartbeat exige perfil habilitado y disponible en DynamoDB; en un `MULTI` renueva `courier:heartbeat:<id>` (TTL `PRESENCE_TTL_SECONDS`, 60 s), actualiza el ZSET `couriers:available:<zone>` y retira miembros vencidos. Dejar de estar disponible o ser deshabilitado también retira la presencia. Los comercios solo consultan su zona |
| Tracking | `GET /tracking/{token}` | Público; el mismo 404 para token mal formado, inexistente o con secreto incorrecto; responde solo estado, fecha e hitos |
| Analytics | `GET /stores/me/stats?month=YYYY-MM` | Cache-Aside `cache:store:<id>:stats:<mes>` con TTL `REDIS_TTL`; el campo `source` indica `cache` o `dynamodb` |

- La lectura de presencia agrupa los heartbeats con `MGET` (un viaje a Redis por lote).
- Con Redis caído, la presencia responde 503 `DEPENDENCY_UNAVAILABLE`, pero aceptar y entregar siguen protegidos por DynamoDB, y las estadísticas se leen de la tabla.

## Evidencia
- `app/tests/test_http_dispatch_flow.py`: ciclo completo por HTTP, reintento idempotente, segundo repartidor con 409, pedido activo, historial, seguimiento sin datos privados, caché miss/hit/invalidación, cancelación y FAILED, presencia con miembro vencido, salida y Redis caído.
- `app/tests/integration/test_api_flow.py::test_spec05_full_delivery_presence_tracking_and_cache`: el mismo ciclo por API Gateway en MiniStack con Redis real.
- `app/tests/integration/test_concurrency.py`: 100 aceptaciones concurrentes con un único ganador (SPEC-02).
