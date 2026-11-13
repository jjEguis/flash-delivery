# Modelo de persistencia — SPEC-01

Tabla `FlashDeliveryTable`, claves String `PK`/`SK`, índices dispersos `GSI1PK`/`GSI1SK` y `GSI2PK`/`GSI2SK`, proyección ALL. DynamoDB es el estado oficial; la presencia Redis es temporal. No se implementan endpoints ni decisiones de negocio de asignación en esta SPEC.

## Catálogo y convenciones

[Ejemplos JSON](catalogo-items.json): un ítem por tipo y un segundo ORDER para mostrar la diferencia PENDING/ASSIGNED. Son datos sintéticos, no respuestas HTTP. Los registros oficiales se construyen con funciones de los módulos y se validan antes de generar escrituras.

Todos los ítems requieren `entityType`, `schemaVersion=1`, `version` entero positivo, PK y SK. No se aceptan atributos fuera del esquema. Las proyecciones replican la versión y estado del pedido. Las fechas se normalizan a UTC con seis decimales: `2026-01-01T00:01:00.000000Z`; de ese modo las claves se ordenan por tiempo. Un ID ASCII de 1–128 caracteres admite letras, números, guion y guion bajo; no admite separadores `#`, `.` ni caracteres Unicode.

| Tipo / propietario | Campos obligatorios además de los comunes | Opcionales | PK / SK |
| --- | --- | --- | --- |
| STORE / Stores | storeId, ownerId, zoneId, name, enabled, createdAt, updatedAt | Ninguno | STORE#id / PROFILE |
| COURIER / Couriers | courierId, ownerId, zoneId, name, enabled, available, createdAt, updatedAt | Ninguno | COURIER#id / PROFILE |
| ORDER / Orders | orderId, storeId, zoneId, status, createdAt, updatedAt, pickupAddress, dropoffAddress, feeMinor, currency, trackingTokenHash | courierId; obligatorio en ASSIGNED/PICKED_UP/DELIVERED/FAILED y ausente en PENDING | ORDER#id / META |
| ORDER_EVENT / Orders | orderId, eventId, eventType, occurredAt | Ninguno | ORDER#id / EVENT#timestamp#eventId |
| ACTIVE_ASSIGNMENT / Couriers | courierId, orderId, assignedAt | Ninguno | COURIER#id / ACTIVE |
| COURIER_ORDER_VIEW / Couriers | courierId, orderId, storeId, status, createdAt, updatedAt | Ninguno | COURIER#id / ORDER#id |
| STORE_STATUS_VIEW / Orders | storeId, orderId, status, createdAt, updatedAt | Ninguno | STORE#id / STATUS#orderId |
| STORE_STATS / Analytics | storeId, month, deliveredCount, totalFeeMinor, updatedAt | Ninguno | STORE#id / STATS#YYYY-MM |
| IDEMPOTENCY / infraestructura del comando | scope, requestId, payloadHash, result (objeto), createdAt | Ninguno | REQUEST#scope#requestId / IDEMPOTENCY |

Direcciones son texto no vacío en este contrato de almacenamiento; la API detallará su validación en SPEC-03. `feeMinor`, `totalFeeMinor` y `deliveredCount` son enteros no negativos; moneda son tres letras mayúsculas. `enabled`/`available` son booleanos estrictos. Los hashes son SHA-256 hexadecimal. `updatedAt` no puede preceder a `createdAt`. No se permite float: la serialización usa enteros, booleanos, texto, listas, objetos y null. Se acotan números a 38 dígitos y anidamiento a 32 niveles.

Los atributos GSI son obligatorios únicamente para las variantes que participan en el índice:

| Ítem | GSI1PK / GSI1SK | GSI2PK / GSI2SK |
| --- | --- | --- |
| ORDER, cualquier estado | STORE#storeId / ORDER#createdAt#orderId | Solo PENDING: ZONE#zoneId#OPEN / CREATED#createdAt#orderId |
| COURIER_ORDER_VIEW | COURIER#courierId / ORDER#createdAt#orderId | Ausentes |
| STORE_STATUS_VIEW | Ausentes | STORE#storeId#status / CREATED#createdAt#orderId |
| Otros tipos | Ausentes | Ausentes |

No se conserva un atributo de índice como null: ambos atributos se omiten cuando no aplican. Sustituir el registro oficial de PENDING por otro estado retira las claves GSI2 de zona; su vista de comercio conserva GSI2 con la nueva partición de estado. GSI1 del pedido permanece para el historial del comercio y el de la vista courier conserva el historial del repartidor.

## Patrones de acceso

Los nombres usados en expresiones se aliasan (`#pk`, `#sk`, `#version`, etc.) para evitar palabras reservadas. `p` es la partición y `s` el prefijo de la siguiente tabla. Las Query utilizan `#pk = :pk AND begins_with(#sk, :prefix)`; para fecha inicial/final utilizan `#pk = :pk AND #sk BETWEEN :lo AND :hi`. No emplean Scan ni FilterExpression.

| Patrón | Repositorio / operación | Clave o p / s | Consistencia | Paginación y orden |
| --- | --- | --- | --- | --- |
| AP01 | Stores.get_profile, GetItem | STORE#id / PROFILE | Fuerte | No aplica |
| AP02 | Couriers.get_profile, GetItem | COURIER#id / PROFILE | Fuerte | No aplica |
| AP03 | Orders.get_order, GetItem | ORDER#id / META | Fuerte | No aplica |
| AP04 | Orders.list_events, Query base | ORDER#id / EVENT# | Fuerte | Cursor; ascendente |
| AP05 | Orders.list_store_orders, Query GSI1 | STORE#id / ORDER# | Eventual | Cursor; descendente |
| AP06 | Orders.list_store_orders_by_status, Query GSI2 | STORE#id#status / CREATED# | Eventual | Cursor; descendente |
| AP07 | Couriers.list_orders, Query GSI1 | COURIER#id / ORDER# | Eventual | Cursor; descendente |
| AP08 | Orders.list_open_orders, Query GSI2 | ZONE#id#OPEN / CREATED# | Eventual | Cursor; ascendente |
| AP09 | Couriers.get_active, GetItem | COURIER#id / ACTIVE | Fuerte | No aplica |
| AP10 | Availability.list_present, ZRANGEBYSCORE + GET | couriers:available:zoneId; courier:heartbeat:courierId | Presencia efímera | Cursor score/courierId; ascendente |
| AP11 | Tracking.get_tracking, GetItem + Query | Token → ORDER#id / META, luego ORDER#id / EVENT# | Fuerte por operación; no es snapshot común | Cursor de eventos |
| AP12 | Analytics.get_month, GetItem | STORE#id / STATS#YYYY-MM | Fuerte | No aplica |

El acceso técnico adicional `IdempotencyRepository.get_result` usa GetItem fuerte de REQUEST#scope#requestId / IDEMPOTENCY. `scope` se construye con el ID del actor y una operación versionada, por ejemplo `actor:orders.create.v1`. Retención y respuesta a reintentos quedan para SPEC-02; no se habilita TTL para estos registros.

## Cursores y fechas

Los repositorios devuelven `Page(items, next_cursor)` y aceptan `limit` entre 1 y 100. El cursor base64 transporta la LastEvaluatedKey y un identificador SHA-256 de la consulta: partición, índice, prefijo, dirección y rango. Se rechaza cuando cambia esa consulta o contiene claves incompatibles. Se puede cambiar el tamaño de página.

Los rangos `start`/`end` incluyen los instantes extremos; el límite superior agrega `#~`, por encima de los IDs ASCII admitidos, para incluir todos los desempates del instante final. Un cursor puede conducir a una página vacía al finalizar: solo su ausencia confirma que no hay otra página. Las inserciones concurrentes no ofrecen una vista congelada.

Estos cursores no están firmados ni constituyen autorización; las rutas futuras deberán verificar actor y pertenencia en cada llamada. No se filtra una consulta por el cursor recibido: la partición siempre la fija el repositorio. Las lecturas GSI no autorizan una aceptación; SPEC-02 revalidará condiciones en la tabla base.

## Seguimiento y presencia

El token tiene formato `orderId.secret`, con secreto aleatorio de 32 bytes codificado URL-safe. Solo SHA-256 del secreto se guarda en META. La lectura valida el formato, obtiene el pedido por clave y compara el hash con tiempo constante antes de consultar eventos. La respuesta elimina direcciones, tarifa, IDs de participantes, claves físicas y hashes: solo entrega ID, estado, fecha de actualización y hitos paginados. Tracking consume un protocolo `OrderReader`, sin importar implementaciones privadas de Orders.

El generador de tokens existe para concretar el acceso sin Scan; su emisión HTTP, revocación y tratamiento del resultado idempotente se definirán en las siguientes SPEC. No se guarda el secreto en el catálogo ni en registros idempotentes del seed.

En Redis, el ZSET usa courierId como miembro y epoch de último heartbeat como score. Se filtra por ventana vigente, se comprueba que exista la clave con TTL, y que zona y epoch coincidan con el candidato. Se omiten miembros vencidos, cambiados de zona, inválidos o con JSON corrupto. El cursor desempata scores iguales por courierId. La página no es un snapshot y debe renovarse frente a cambios concurrentes. No se modifica disponibilidad persistida ni se adjudican pedidos desde esta lectura.

## Escrituras transaccionales

Cada repositorio produce descriptores sin confirmar cambios. `build_put` crea con condición de ausencia o sustituye con `expected_version`; en reemplazos exige versión anterior + 1. La sustitución completa elimina atributos GSI obsoletos. Cada módulo solo construye puts de sus tipos. Stores expone condición de habilitación/versionado; Couriers de habilitación, disponibilidad, zona y versión, además de liberación ACTIVE condicionada al orderId esperado.

La composición debe escribir META, evento y vistas necesarias en una misma llamada `transact_write_items`. El adaptador rechaza tablas ajenas, claves inválidas, acciones desconocidas, dos acciones sobre un mismo PK/SK, transacciones vacías o de más de 100 acciones. Estos son mecanismos de almacenamiento; la composición completa de crear/aceptar/entregar y sus invariantes de concurrencia corresponde a SPEC-02.

Se comprueba máximo de clave en UTF-8: PK 2048 bytes y SK 1024, también en índices. El tamaño del JSON AttributeValue debe caber en 400 KiB por ítem y el JSON de la transacción en 4 MiB: son umbrales conservadores que pueden rechazar antes que el servicio porque cuentan envolturas JSON. No se afirma un cálculo exacto del tamaño facturable.

Referencias oficiales: [límites DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html), [paginación Query](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Query.Pagination.html) y [TransactWriteItems](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html).

## Seed y pruebas

```bash
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo --clean
docker compose exec -T cdk-dev python -m pytest tests/test_access_patterns.py tests/test_storage_model.py -v
docker compose exec -T cdk-dev python -m pytest tests/integration/test_data_model.py -m integration -v
```

El seed exige namespace reservado `SEED_` de hasta 64 caracteres; genera IDs y fechas deterministas, un comercio, tres repartidores, siete pedidos, eventos, vistas, ACTIVE, agregado e idempotencia. Repetirlo sobrescribe únicamente sus claves conocidas. La limpieza reconstruye esas claves y usa Delete, ZREM y DEL; no recorre la tabla ni vacía Redis. El estado sintético no se debe mezclar con datos de uso real. Los secretos deterministas del seed son exclusivamente de demostración; la creación normal usará aleatoriedad.

Los unitarios usan moto/fakeredis y registran claves, expresiones, índice y consistencia de las llamadas. Verifican los doce patrones, todas las páginas, rangos, rechazo de cursores cruzados, límites, sustitución de índices, rollback y limpieza del seed. La integración repite los doce accesos con namespace UUID y espera convergencia de GSIs en MiniStack. Todavía no acredita carreras de asignación ni autorización HTTP.
