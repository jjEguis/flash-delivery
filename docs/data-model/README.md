# Modelo físico vigente — DynamoDB y Redis

Revisión: 2026-11-18, implementación hasta SPEC-10. La [guía general](../ARQUITECTURA_GENERAL.md) explica los motivos y ejemplos paso a paso; este documento fija el contrato de almacenamiento. La [matriz AP01–AP16](../data-access-patterns.md) identifica consultas y consumidores. Fuente ejecutable: [model.py](../../app/lambdas/shared/storage/model.py), [keys.py](../../app/lambdas/shared/storage/keys.py), [repositorios](../../app/lambdas/).

## Tabla, tipos y convenciones

`FlashDeliveryTable`: primary key compuesta por `PK` (partition key String) y `SK` (sort key String). GSI1 usa GSI1PK/GSI1SK y GSI2 usa GSI2PK/GSI2SK, todos String, proyección ALL y facturación PAY_PER_REQUEST. No hay LSI ni TTL DynamoDB configurados. El nombre de tabla puede configurarse; el anterior es el valor del proyecto.

Cada ítem requiere PK, SK, `entityType`, `schemaVersion=1` y `version` entero positivo. Hay **11 tipos de ítem**. Las vistas de pedido copian estado/versión de META; eventos, ACTIVE, credenciales e intenciones tienen su propia versión. No se permiten atributos fuera del esquema validado.

| Tipo | Atributos de negocio obligatorios además de los comunes | Opcionales |
| --- | --- | --- |
| STORE | storeId, ownerId, zoneId, name, enabled, createdAt, updatedAt | approvalStatus; las altas nuevas lo incluyen |
| COURIER | courierId, ownerId, zoneId, name, enabled, available, createdAt, updatedAt | approvalStatus; las altas nuevas lo incluyen |
| ORDER | orderId, storeId, zoneId, status, createdAt, updatedAt, pickupAddress, dropoffAddress, feeMinor, currency, trackingTokenHash | courierId según estado; pickupCoordinates y dropoffCoordinates juntos |
| ORDER_EVENT | orderId, eventId, eventType, occurredAt | Ninguno |
| ACTIVE_ASSIGNMENT | courierId, orderId, assignedAt | Ninguno |
| COURIER_ORDER_VIEW | courierId, orderId, storeId, status, createdAt, updatedAt | Ninguno |
| STORE_STATUS_VIEW | storeId, orderId, status, createdAt, updatedAt | Ninguno |
| STORE_STATS | storeId, month, deliveredCount, totalFeeMinor, updatedAt | Ninguno |
| IDEMPOTENCY | scope, requestId, payloadHash, result, createdAt | Ninguno |
| TRACKING_ACCESS | orderId, nonce, expiresAt, revoked | Ninguno |
| PROFILE_AUDIT | profileKind, profileId, eventId, actorId, occurredAt, fromStatus, toStatus, profileVersion, reason | Ninguno |

`version` de PROFILE_AUDIT no es `profileVersion`: el primero identifica la versión del evento; el segundo, la versión del perfil tras la decisión. Una revocación modifica `revoked` sin incrementar las versiones del pedido; no todos los cambios técnicos incrementan el atributo version.

### Validación de valores

- IDs: 1–128 caracteres ASCII, letras/números/guion/guion bajo, sin `#` ni `.`. Los IDs generados por `clock.new_id` combinan prefijo, milisegundos hexadecimales y aleatoriedad; no son ULID/UUID estándar. Las pruebas también usan UUID para namespaces aislados.
- Fechas: UTC con seis decimales y Z, por ejemplo `2026-11-18T15:00:00.000000Z`. `updatedAt` no precede a createdAt. Mes: YYYY-MM válido.
- Booleanos estrictos; números monetarios y contadores enteros no negativos en almacenamiento. La API exige feeMinor positivo y acotado. `currency`: tres letras mayúsculas; la aplicación usa COP. No convertir importes a float.
- JSON sin float/binarios; enteros hasta 38 dígitos, profundidad hasta 32 niveles. El límite local de 400 KiB usa una estimación conservadora sobre JSON AttributeValue, no el cálculo exacto de bytes facturables del motor.
- Estado de pedido: PENDING, ASSIGNED, PICKED_UP, DELIVERED, CANCELLED, FAILED. ASSIGNED/PICKED_UP/DELIVERED/FAILED requieren courierId; PENDING lo prohíbe. CANCELLED puede conservarlo si hubo asignación.
- Coordenadas estáticas: mapas `{latitudeE6, longitudeE6}` de enteros; ambos puntos presentes o ambos ausentes. No hay muestras de movimiento DynamoDB. Validación de cobertura y entrada decimal: capa Tracking/Orders.
- Perfil: approvalStatus en PENDING/ENABLED/SUSPENDED; compatible con enabled. Perfil habilitado implica ENABLED. Un perfil suspendido tiene enabled=false; suspender repartidor fuerza available=false.
- Auditoría: profileKind STORE/COURIER, profileVersion al menos 2 y motivo de 1–300 caracteres tras quitar espacios exteriores. Retención indefinida en la demo.
- TRACKING_ACCESS: nonce base64url de 43 caracteres, expiresAt epoch positivo, revoked booleano. El token público se deriva con HMAC; META guarda SHA-256 del secreto, no el enlace completo.

## Claves base: localización y motivo

| Tipo | PK | SK | Razón del formato |
| --- | --- | --- | --- |
| STORE | STORE#storeId | PROFILE | Un perfil por comercio, lectura directa |
| COURIER | COURIER#courierId | PROFILE | Perfil único independiente de su estado |
| ORDER | ORDER#orderId | META | Estado oficial consultable por ID desde distintos actores |
| ORDER_EVENT | ORDER#orderId | EVENT#occurredAt#eventId | Colección temporal de eventos de una entrega |
| ACTIVE_ASSIGNMENT | COURIER#courierId | ACTIVE | Clave fija compartida por todos los intentos de aceptar del repartidor |
| COURIER_ORDER_VIEW | COURIER#courierId | ORDER#orderId | Vista estable del historial de ese repartidor |
| STORE_STATUS_VIEW | STORE#storeId | STATUS#orderId | Vista estable aunque cambie su estado |
| STORE_STATS | STORE#storeId | STATS#YYYY-MM | Un agregado por comercio y mes |
| IDEMPOTENCY | REQUEST#scope#requestId | IDEMPOTENCY | Una intención por actor/operación/clave |
| TRACKING_ACCESS | ORDER#orderId | TRACKING | Revocar/expirar credencial sin cambiar META/vistas |
| PROFILE_AUDIT | PROFILE_AUDIT#profileKind#profileId | EVENT#occurredAt#eventId | Decisiones de un perfil, independientes del administrador que actuó |

`scope=actorId:operacion.version`, por ejemplo `S01:orders.create.v1` para un actor sintético; las operaciones reales se asignan según su rol. `requestId` del ítem es la Idempotency-Key recibida, no el identificador de trazabilidad HTTP. Los separadores se introducen solo en las funciones de claves.

El par PK/SK es único en la tabla. Un `attribute_not_exists(PK)` evaluado sobre el ítem al que apunta la escritura compuesta comprueba su ausencia; no prohíbe otros ítems con esa PK y otra SK.

## Índices dispersos compartidos

| Ítem | GSI1PK / GSI1SK | GSI2PK / GSI2SK |
| --- | --- | --- |
| ORDER, todo estado | STORE#storeId / ORDER#createdAt#orderId | Solo PENDING: ZONE#zoneId#OPEN / CREATED#createdAt#orderId |
| COURIER_ORDER_VIEW | COURIER#courierId / ORDER#createdAt#orderId | Ausentes |
| STORE_STATUS_VIEW | Ausentes | STORE#storeId#status / CREATED#createdAt#orderId |
| STORE | Ausentes | ADMIN#STORE#approvalStatus / CREATED#createdAt#storeId |
| COURIER | Ausentes | ADMIN#COURIER#approvalStatus / CREATED#createdAt#courierId |
| Los otros seis tipos | Ausentes | Ausentes |

Los dos atributos de cada índice se omiten juntos cuando no corresponde; no se guardan como null. ALL copia los atributos del ítem al índice; no significa que sus DTOs HTTP expongan todos esos campos. Cada servicio construye su proyección pública.

Un META puede tener una sola entrada por GSI. Las vistas separadas aportan las entradas adicionales necesarias por repartidor y por estado del comercio. El motor replica índices automáticamente; el código debe escribir las vistas. Consultar un índice no ofrece consistencia fuerte ni una relación de unicidad sobre sus valores.

La sustitución condicional de META al salir de PENDING elimina sus claves de abiertos; STORE_STATUS_VIEW conserva GSI2 pero cambia su grupo de estado. El historial GSI1 conserva createdAt. Las bandejas administrativas se ordenan por creación del perfil, no por última decisión.

## Consistencia, páginas y rangos

`Repository.get` y Query base usan ConsistentRead=true; Query GSI1/GSI2 no. `limit` está entre 1 y 100; el cursor contiene versión de formato, huella de consulta y LastEvaluatedKey. Se valida la partición/prefijo/índice/dirección/rango y las claves incluidas; cambiar de consulta invalida el cursor. El cursor no está firmado y no autoriza acceso.

Las consultas de historial aceptan rangos start/end mediante el repositorio; el contrato de cada ruta determina qué parámetros expone. `BETWEEN` incluye extremos; el límite superior incorpora `#~` para abarcar IDs de un mismo instante. No hay snapshot entre páginas ni orden causal global de eventos entre relojes.

Las bandejas administrativas revalidan cada perfil devuelto por GSI con GetItem fuerte y descartan filas cuyo estado ya cambió. Eso puede producir menos de limit resultados, incluso cero, con nextCursor. La relectura evita mostrar el estado obsoleto de esa fila; no vuelve fuerte al índice ni garantiza que ya aparezcan todos los registros recién insertados.

## Escrituras e invariantes

Crear/aceptar/recoger/entregar/cancelar/fallar mantienen META, evento y vistas necesarias en un commit; los comandos de pedidos añaden resultado idempotente. Aceptar añade elegibilidad de perfil y Put de ACTIVE si no existe. Liberar ACTIVE exige el orderId esperado para no borrar la asignación de otra entrega.

Las transiciones usan Put completo con versión esperada. Agregados usan ADD en el commit de entrega, no CAS sobre un snapshot del contador. La condición de transición y el registro idempotente evitan sumar dos veces. PROFILE_AUDIT y perfil se confirman juntos; suspender repartidor añade ConditionCheck de ausencia de ACTIVE. No hay un commit distribuido con Redis.

No hay borrado rutinario de eventos, idempotencia ni auditoría, y no se habilita TTL para ellos. expiresAt de credencial es una condición lógica en aplicación. Cambiar retención requiere especificar qué garantías se mantienen tras expirar un resultado idempotente o eliminar eventos.

## Redis: datos efímeros y caché

| Familia | Estructura | Uso |
| --- | --- | --- |
| courier:heartbeat:courierId | String JSON con TTL | Señal reciente por repartidor |
| couriers:available:zoneId | ZSET | Descubrimiento por zona y tiempo |
| cache:store:storeId:stats:month | String JSON con TTL | Cache-Aside del agregado DynamoDB |
| tracking:order:orderId:latest | String JSON, actualización Lua | Última muestra, orden/secuencia, TTL y parada |
| tracking:order:orderId:route:phase | String JSON | Snapshot de ruta, segmentos y progreso |
| Locks/cooldown/rate limits/contador de Tracking | Strings/contadores con expiración | Coordinación temporal de cálculo y publicación |

Los nombres completos y TTL específicos de Tracking están en [guía GEO](../geo/README.md) y `tracking/routes.py`, `location_store.py`. Redis no decide asignación ni reemplaza ACTIVE. Hay coordenadas de movimiento en Redis, nunca una colección histórica de posiciones en esta tabla.

## Migración y ejemplos

Perfiles anteriores a SPEC-10 requieren [backfill](../admin/README.md): Scan paginado solo de mantenimiento y Update condicional por versión/enabled/estado previo. Añade approvalStatus/GSI2PK/GSI2SK. No modifica permisos/versiones ni crea auditoría retroactiva. Si hay conflictos concurrentes, omite esos perfiles y se puede repetir.

[Catálogo JSON](catalogo-items.json): ejemplos sintéticos de todos los tipos, con claves/atributos compatibles con `model.validate`. No es una respuesta HTTP ni una copia del entorno. Sus ejemplos de auditoría/credencial son ilustraciones independientes, no un único snapshot transaccional para cargar directamente. El seed de datos de SPEC-01 sigue generando su conjunto original de nueve tipos; el catálogo incluye además TRACKING_ACCESS y PROFILE_AUDIT, sin cambiar lo que carga ese script.

```bash
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo --clean
docker compose exec -T cdk-dev python -m pytest tests/test_storage_model.py tests/test_access_patterns.py tests/test_approvals.py -q
docker compose exec -T cdk-dev python -m pytest tests/integration/test_data_model.py tests/integration/test_approvals_http.py -m integration -q
```

El namespace reservado del seed y sus claves deterministas permiten limpiar sin Scan. No debe confundirse ese conjunto con las altas normales, que generan IDs y credenciales según su caso de uso.
