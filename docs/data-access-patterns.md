# Patrones de acceso vigentes — AP01 a AP16

Revisión: 2026-11-18, hasta SPEC-10. Reemplaza la propuesta de fase 1 conservada en Git. [Motivación de las claves](ARQUITECTURA_GENERAL.md), [esquema físico](data-model/README.md), [OpenAPI](api/openapi.json). No hay estado OPEN de negocio ni ítem ORDER/ASSIGNMENT: se usa PENDING y COURIER/ACTIVE.

## Matriz de acceso

`p / s` indica partition key y sort key/prefijo de la tabla o índice indicado. Las rutas se muestran sin el prefijo común `/api/v1`. Detalle de parámetros y respuestas: OpenAPI. AP15/AP16 hacen explícitos accesos técnicos ya existentes; su numeración no añade endpoints ni cambia AP01–AP14.

| ID / pregunta | Operación y clave | Consistencia / orden | Consumidor o ruta |
| --- | --- | --- | --- |
| AP01 Perfil de comercio | GetItem STORE#id / PROFILE | Fuerte; un ítem | Stores.get_my_store; creación; GET /stores/me |
| AP02 Perfil de repartidor | GetItem COURIER#id / PROFILE | Fuerte; un ítem | Couriers, Dispatch, Availability; GET /couriers/me |
| AP03 Pedido por ID | GetItem ORDER#id / META | Fuerte; un ítem | Orders/Dispatch/Tracking; GET /orders/{orderId} |
| AP04 Eventos del pedido | Query base ORDER#id / EVENT# | Fuerte; ascendente, cursor | GET /orders/{orderId}/events; seguimiento público |
| AP05 Historial completo del comercio por creación | Query GSI1 STORE#id / ORDER# | Eventual; descendente, cursor/rango | GET /stores/me/orders sin status |
| AP06 Pedidos de comercio por estado | Query GSI2 STORE#id#status / CREATED# | Eventual; descendente, cursor/rango | GET /stores/me/orders con status |
| AP07 Historial de repartidor | Query GSI1 COURIER#id / ORDER# | Eventual; descendente por creación del pedido, cursor/rango | GET /couriers/me/orders |
| AP08 Ofertas pendientes de zona | Query GSI2 ZONE#id#OPEN / CREATED# | Eventual; ascendente, cursor | GET /orders/available; zona validada contra perfil |
| AP09 Asignación activa | GetItem COURIER#id / ACTIVE; después META si existe | Fuerte por lectura; sin snapshot conjunto | GET /couriers/me/active; guard de aceptación y suspensión |
| AP10 Presencia reciente de zona | Redis ZRANGEBYSCORE + lectura de heartbeat con TTL | Efímera; orden por score/ID, cursor propio | GET /zones/{zoneId}/couriers |
| AP11 Seguimiento por token | Resolver ID/hash contra META + credencial AP15 si existe + AP04 | Fuerte por operación; sin snapshot conjunto | GET /tracking/{token}; DTO mínimo |
| AP12 Estadística mensual | Cache-Aside Redis; GetItem STORE#id / STATS#YYYY-MM en miss/fallo | Caché temporal; base fuerte | GET /stores/me/stats |
| AP13 Bandeja administrativa por tipo/estado | Query GSI2 ADMIN#kind#estado / CREATED# + GetItem de cada perfil | Índice eventual y relectura fuerte; descendente, cursor | GET /admin/stores, /admin/couriers |
| AP14 Auditoría de perfil | Query base PROFILE_AUDIT#kind#id / EVENT# | Fuerte; descendente, cursor | GET /admin/stores/{id}/events, /admin/couriers/{id}/events |
| AP15 Credencial de seguimiento | GetItem ORDER#id / TRACKING | Fuerte; un ítem | TrackingAccess.for_order; geografía pública y validación de enlaces nuevos |
| AP16 Resultado idempotente | GetItem REQUEST#actor:operation#requestId / IDEMPOTENCY | Fuerte; un ítem | run_command: antes de escribir y tras conflicto/reintento |

El detalle administrativo reutiliza AP01/AP02; para repartidor añade AP09. Las lecturas geográficas autenticadas usan AP03 y Redis; las públicas también validan AP15. Geometría/progreso se sirven desde el snapshot de ruta Redis o proveedor OSRM, no desde un nuevo índice DynamoDB.

AP11 admite tokens históricos sin TRACKING solo para estados; si existe una credencial expirada/revocada, el enlace se rechaza también para estado. Ubicación/ruta exige que TRACKING exista y que el pedido esté activo.

## Cómo se implementa la Query

`Repository.query` fija la partición desde el caso de uso y utiliza alias para claves; no obtiene el ámbito a partir de un cursor no confiable. Las condiciones son igualdad de partition key y begins_with de sort key, o BETWEEN con fechas normalizadas. No se usa FilterExpression en los accesos DynamoDB de la matriz.

Ejemplo de AP06:

```text
IndexName = GSI2
KeyConditionExpression = #pk = :pk AND begins_with(#sk, :prefix)
ExpressionAttributeNames = {#pk: GSI2PK, #sk: GSI2SK}
Valores conceptuales = {:pk: STORE#S01#ASSIGNED, :prefix: CREATED#}
ScanIndexForward = false
```

Un limit de 25 pide una página de hasta 25 ítems evaluados, no todos los resultados. Se sigue LastEvaluatedKey mediante nextCursor; una página vacía no obliga a terminar si hay cursor. La relectura de AP13 puede descartar perfiles cuyo estado ya cambió. El conjunto no queda congelado entre páginas.

## Permisos y consistencia

El repositorio implementa lectura física; la autorización pertenece al servicio/handler. Conocer `ORDER#id` o un cursor no concede acceso. El actor y su rol determinan el comercio, repartidor y zona autorizados; ADMIN no recibe acceso GPS por consultar un pedido.

AP08 permite descubrir candidatos, pero aceptar siempre vuelve a validar META, versión del perfil y ausencia de ACTIVE en un commit. AP13 revalida estado para presentar filas actuales, pero una inserción puede tardar en aparecer. Las listas de pedidos no prometen una relectura fuerte de cada fila del GSI.

## Accesos que no están implementados

No hay búsqueda por nombre, consultas globales de todos los pedidos, auditoría por administrador, reporte arbitrario por tarifa ni selección de repartidor más cercano mediante índice geoespacial. Esos requisitos necesitarían sus propias claves/índices, vistas o proceso analítico. Las claves físicas no sustituyen ese análisis.

Scan existe en `scripts.backfill_approvals` por mantenimiento y en `scripts.benchmark` para comparar estrategias. No es una consulta operativa escondida detrás de los endpoints. Los datos de pruebas se limpian por sus claves conocidas; no se vacía la tabla compartida.

## Evidencias

- `tests/test_access_patterns.py` y `tests/integration/test_data_model.py`: accesos originales, índices, paginación y consistencia.
- `tests/test_approvals.py` y `tests/integration/test_approvals_http.py`: AP13/AP14, cursor por ámbito, GSI obsoleto, permisos, auditoría y carreras de suspensión.
- `tests/test_commands.py`, `tests/test_gps_tracking.py`, `tests/integration/test_geo_http_integration.py`: comandos, credenciales y seguimiento.
- [Registro de validación](validation.md): conteos/fecha de las ejecuciones y limitaciones del emulador.
