# SPEC-06 — Calidad, rendimiento y evidencia

**Estado:** implementada; resultados en el [informe de calidad](../informe-calidad.md).

## Objetivo
Demostrar propiedades técnicas y documentar límites del sistema.

## Pruebas
- Concurrencia: 100 aceptaciones por pedido, una ganadora.
- Datos sintéticos: 10k y 100k pedidos, si la capacidad local lo permite.
- Accesos: Query/GetItem frente a Scan evitado; contar lecturas y latencia.
- Redis: hit/miss, TTL, fallo y recuperación.
- API: permisos, validación, paginación, idempotencia.
- Métricas: p50/p95, errores, throughput, caché; registrar máquina y configuración de pruebas.

## Aceptación
Scripts reproducibles, informe de resultados, limitaciones de MiniStack, conclusiones sin afirmar que NoSQL es universalmente superior a SQL.

## Implementación y evidencia
- `app/scripts/benchmark.py`: carga N pedidos sintéticos en un namespace propio, mide AP03/AP05/AP06/AP08 frente a un Scan equivalente (ítems leídos y latencia), la caché de estadísticas (miss/hit/TTL), 100 aceptaciones concurrentes y la API HTTP; registra máquina y configuración, y limpia por claves exactas.
- [`docs/informe-calidad.md`](../informe-calidad.md) con resultados de 10 000 pedidos, limitaciones de MiniStack y conclusiones. Datos crudos en `docs/evidencias/benchmark-10k.json`.
- Permisos, validación, paginación, idempotencia, TTL y caída de Redis están cubiertos por la suite automatizada (115 pruebas).
- 100 000 pedidos: no ejecutado; el emulador escribe unos 70 ítems/s (unos 46 minutos estimados). El script lo admite con `--orders 100000`.
