# SPEC-05 — Dispatch, Availability, Tracking y Analytics

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
