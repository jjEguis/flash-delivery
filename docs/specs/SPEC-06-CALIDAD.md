# SPEC-06 — Calidad, rendimiento y evidencia

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
