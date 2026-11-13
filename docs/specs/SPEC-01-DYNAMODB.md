# SPEC-01 — DynamoDB Single Table Design

**Estado:** implementada; validación y PR hacia develop forman parte de esta entrega.

Contrato detallado en [modelo de persistencia](../data-model/README.md), con [catálogo JSON](../data-model/catalogo-items.json), claves, atributos requeridos/opcionales, matriz AP01–AP12, cursores, consistencia y límites.

## Objetivo
Implementar la tabla y sus accesos sin `Scan` en rutas operativas.

## Contrato de claves
- PK/SK String; GSI1PK/GSI1SK String; GSI2PK/GSI2SK String.
- Tipos: STORE PROFILE, COURIER PROFILE/ACTIVE/ORDER#, ORDER META/EVENT#, STORE STATUS#/STATS#, REQUEST IDEMPOTENCY.
- Timestamps UTC ISO 8601, IDs únicos, `version` entero; los nombres de atributos de índice son literales y estables.

## Patrones obligatorios
AP01 perfil comercio GetItem; AP02 perfil courier GetItem; AP03 pedido GetItem; AP04 eventos Query; AP05 pedidos comercio GSI1; AP06 comercio por estado GSI2; AP07 historial courier GSI1; AP08 abiertos zona GSI2; AP09 activo courier GetItem; AP10 disponibilidad Redis; AP11 seguimiento GetItem+Query; AP12 agregado mensual GetItem.

## Entregables
- Catálogo de ítems JSON con ejemplo por tipo y atributos obligatorios/opcionales.
- Tabla de patrones con `KeyConditionExpression`, paginación y consistencia.
- Funciones puras de generación de PK/SK y claves GSI.
- Repositorios por módulo y constructores de escrituras transaccionales.
- Seed de datos sintéticos y pruebas de consultas.

## Invariantes
- Un pedido pendiente tiene claves de GSI2 zona; otro estado no las tiene.
- Toda entrega tiene vista de comercio por estado; si asignada, vista de courier.
- El GSI1 del pedido conserva historial de comercio; el de la vista courier conserva historial de courier.
- La proyección de estado refleja el estado oficial después de cada commit.

## Aceptación
Para cada patrón AP01–AP12 existe prueba que demuestra la clave usada, paginación cuando corresponda y ausencia de Scan. Validar límites de tamaño y claves reservadas.

## Evidencia de implementación

- `app/lambdas/shared/storage/`: esquema, claves, serialización, Page/cursor y descriptores transaccionales.
- Repositorios de Stores, Couriers, Orders, Analytics y persistencia de idempotencia; participación en transacciones mediante condiciones, creación, sustitución versionada y eliminación condicional.
- Availability: lectura paginada de presencia ZSET + heartbeat con TTL; Tracking: ID del pedido más secreto, hash en META y consulta de eventos por clave.
- `app/scripts/seed_data.py`: 43 ítems sintéticos deterministas para nueve tipos y todos los estados, escritura repetible y limpieza por claves exactas.
- `app/tests/test_access_patterns.py` y `test_storage_model.py`: claves/expresiones/consistencia, paginación y rangos, cursores incompatibles, índices dispersos, tipos, tamaños, propiedad de ítems y guardas transaccionales con moto/fakeredis.
- `app/tests/integration/test_data_model.py`: AP01–AP12 y sustitución transaccional de proyecciones sobre MiniStack/Redis reales, con namespace UUID y limpieza acotada.

## Límite del incremento

No incorpora endpoints, autorización HTTP, composición de casos de uso ni resolución de reintentos de negocio. Los repositorios entregan primitivas; los comandos deben componer META, evento y vistas en una transacción. Aceptación competitiva, entrega y métricas exactamente una vez se validarán en SPEC-02/05. Los cursores no son credenciales ni están firmados; la autorización futura debe comprobarse independientemente de ellos.
