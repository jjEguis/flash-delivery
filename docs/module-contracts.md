> Documento histórico de fase 1. Para el diseño vigente consultar [arquitectura general](ARQUITECTURA_GENERAL.md) y [especificaciones](specs/README.md). Sus diferencias no deben trasladarse a código sin reconciliación.

# Contratos entre módulos — diseño v1

Este documento define el siguiente incremento. Las firmas son contratos de diseño,
no APIs ya implementadas. No se añaden endpoints, persistencia de negocio ni servicios.
La infraestructura de fase 1 fue validada por el usuario en su terminal.

## Convenciones

Las llamadas serán funciones Python síncronas dentro del monolito. Cada proveedor
expondrá un archivo público `contracts.py` con DTOs inmutables y `Protocol` cuando
se implemente su primer caso de uso. Los consumidores dependen de esos contratos,
y la composición conecta implementaciones; no se importan repositorios ajenos.
Los DTOs no exponen boto3, claves DynamoDB ni clientes Redis.

IDs son cadenas opacas generadas por el servidor; fechas UTC RFC 3339; coordenadas
latitud [-90, 90] y longitud [-180, 180]. Cada operación recibe `RequestContext`
con `request_id`, `actor_id` y `actor_kind` (STORE o COURIER). Un futuro adaptador de
identidad construirá ese contexto; no se acepta identidad arbitraria del cuerpo HTTP.
No se implementa autenticación en este incremento documental.

Escrituras externas requieren `idempotency_key`, acotada por actor y operación.
Consultas paginadas reciben `limit` entre 1 y 100 y cursor opaco; devuelven `items`
y `next_cursor`. La implementación validará que el cursor corresponde a consulta y
actor. La autorización se evalúa también para consultas y reintentos idempotentes.

## Responsabilidades y puertos públicos

| Módulo proveedor | Contrato previsto | Resultado y consumidores |
| --- | --- | --- |
| identity | `resolve_actor(credentials) -> ActorContext` | Identidad verificada para la capa de entrada; detalle de credenciales pendiente |
| stores | `get_store(store_id) -> StoreView`; `require_active_store(store_id, actor) -> StoreSnapshot` | Orders verifica pertenencia y actividad al publicar |
| couriers | `get_courier(courier_id) -> CourierView`; `require_active_courier(courier_id, actor) -> CourierSnapshot` | Dispatch valida pertenencia y habilitación al aceptar |
| orders | `publish_order(context, PublishOrder) -> OrderView` | Publica solicitud de entrega del comercio |
| orders | `get_order(context, order_id) -> OrderView`; `list_store_orders(context, store_id, page) -> Page[OrderSummary]` | Consulta autorizada por comercio, o repartidor asignado para el detalle |
| orders | `list_open_orders(context, zone_id, page) -> Page[OrderSummary]` | Ofertas para repartidores; listados eventualmente consistentes |
| dispatch | `accept_order(context, AcceptOrder) -> AssignmentView`; `get_assignment(context, order_id) -> AssignmentView` | Única puerta de aceptación, consulta autorizada por participantes |
| availability | `heartbeat(context, Heartbeat) -> AvailabilityView`; `go_offline(context) -> None`; `list_available_couriers(zone_id, page) -> Page[CourierPresence]` | Presencia orientativa para Dispatch; no decide la unicidad de aceptación |
| tracking | `record_location(context, LocationUpdate) -> TrackingView`; `get_latest_location(context, order_id) -> TrackingView` | Solo el repartidor asignado escribe; participantes leen |
| analytics | `consume(event) -> None`; `get_store_daily_metrics(context, store_id, date) -> MetricsView` | Proyección futura, sin consultas Scan sobre pedidos |

`StoreView`: store_id, owner_id, active, zone_id. `CourierView`: courier_id,
owner_id, active. Los snapshots agregan `version` para detectar cambios concurrentes.
`PublishOrder`: store_id, pickup_address, dropoff_address, zone_id, idempotency_key.
Las direcciones y la zona serán validadas; el servidor toma la zona operativa del
comercio y rechaza discrepancias. Tarifas, cobros y geocodificación quedan pendientes.
`OrderView`: order_id, store_id, zone_id, status, created_at, version y, tras aceptar,
courier_id. El DTO público mínimo no expone datos personales del destino en listados.
`AcceptOrder`: order_id, courier_id, idempotency_key.
`AssignmentView`: order_id, courier_id, accepted_at, assignment_id.
`Heartbeat`: zone_id; courier_id se obtiene del contexto y del perfil.
`LocationUpdate`: order_id, latitude, longitude, observed_at, sequence_number,
idempotency_key. Tracking exige una secuencia creciente por entrega/repartidor.

Los módulos de identidad, perfiles y tracking tienen aquí solo contratos de lectura
o comandos necesarios para expresar interacciones; sus CRUD completos no están definidos.

## Propiedad de datos y coordinación

Orders es propietario del estado del pedido. Dispatch es propietario del registro
de asignación. Availability es propietario de la presencia Redis. Tracking escribe
sus propios registros; Analytics escribe sus proyecciones. Compartir tabla no permite
leer ni escribir datos ajenos fuera de un puerto público.

La aceptación necesita una transacción que atraviesa Orders y Dispatch. Para ello,
Orders expondrá un puerto interno explícito al coordinador de Dispatch:
`prepare_acceptance(order_id, courier_id, expected_version, accepted_at) -> AtomicChange`.
Este puerto construye el cambio condicional del pedido, pero no lo confirma. El
coordinador agrega la asignación y el resultado idempotente y realiza un único commit
mediante un `UnitOfWork` técnico. La implementación de `AtomicChange` pertenece a
infraestructura y queda fuera del DTO de negocio. Solo estos puertos autorizan la
participación en una transacción común; no se comparten repositorios.

Stores y Couriers ofrecerán, al implementar el flujo, comprobaciones transaccionales
sobre actividad y versión de sus snapshots. De este modo una deshabilitación concurrente
no queda protegida únicamente por una lectura previa. El coordinador no interpreta
sus claves. Estas comprobaciones pertenecen al mismo commit que publicación/aceptación.

## Estados y aceptación

Para el primer incremento funcional se proponen únicamente `OPEN` y `ASSIGNED`:
publicar crea OPEN; aceptar cambia OPEN a ASSIGNED. No se implementan cancelación,
recogida, entrega completada ni reasignación todavía. No se asume un máximo de una
entrega activa por repartidor: esa regla requiere una decisión de producto adicional.

La presencia por zona ayuda a descubrir disponibilidad y puede expirar en cualquier
momento. El primer flujo no usará Redis como condición atómica de aceptación; verifica
identidad y habilitación persistente. Si se exige presencia vigente al aceptar, habrá
que precisar su semántica ante desconexiones antes de implementar esa restricción.

La garantía requerida es un único repartidor por entrega. Se protege en DynamoDB
condicionando el cambio del pedido a OPEN y la creación de asignación a su ausencia.
Ni un resultado GSI ni un lock Redis conceden la asignación. Un pedido listado podría
haber sido aceptado; la operación devuelve un conflicto de dominio si pierde la carrera.

## Errores e idempotencia

| Código estable | Significado | Reintento |
| --- | --- | --- |
| INVALID_INPUT | DTO inválido o clave idempotente ausente | Corregir entrada |
| FORBIDDEN | Actor sin acceso o perfil inactivo | No automático |
| NOT_FOUND | Recurso inexistente o no visible para ese actor | No automático |
| ORDER_NOT_OPEN | Otro intento cambió el estado del pedido | No automático |
| IDEMPOTENCY_CONFLICT | Misma clave con contenido distinto | Usar intención/clave correcta |
| STALE_LOCATION | Secuencia igual o anterior a la ya registrada | No sobrescribir |
| DEPENDENCY_UNAVAILABLE | DynamoDB/Redis no disponible | Reintentar con la misma clave |

Idempotencia usa una huella canónica de los campos de negocio, sin request_id ni
hora generada. El resultado y la huella se guardan en la misma transacción de la
operación. Mismo actor/operación/clave y misma huella devuelven el resultado previo;
contenido distinto produce IDEMPOTENCY_CONFLICT. La consulta de ese registro se hace
antes de interpretar una condición fallida como ORDER_NOT_OPEN y después de un timeout.
Una falla técnica no se convierte automáticamente en conflicto de negocio.

El contrato propuesto conserva registros idempotentes durante la etapa inicial sin
TTL: el periodo de retención se definirá antes de eliminarlos. No se confía únicamente
en la ventana temporal de ClientRequestToken de DynamoDB.

## Eventos futuros

Envelope v1: event_id, event_type, schema_version=1, occurred_at, aggregate_id,
aggregate_version, correlation_id y payload mínimo. Eventos previstos: OrderPublished
(order_id, store_id, zone_id) y OrderAccepted (order_id, store_id, courier_id).
No incluyen direcciones ni coordenadas. Analytics deduplica por event_id.

La futura entrega será al menos una vez, con consumidores idempotentes. No se ofrece
exactly once ni orden global. Para no perder eventos entre commit y publicación,
se propone outbox transaccional en la misma tabla. El mecanismo de extracción y
reintento se diseñará antes de activar Analytics; no se añaden colas ni workers ahora.

## Secuencia recomendada de implementación

1. DTOs, errores y protocolos del primer flujo; prueba de límites de importación.
2. Perfiles mínimos de comercio/repartidor y contexto local explícito de pruebas.
3. Publicación e idempotencia, con repositorio Orders y prueba de Query.
4. Aceptación atómica e idempotente; prueba concurrente de varios repartidores y
   recuperación tras respuesta perdida. Un ganador y ningún registro parcial.
5. Presencia Redis y tracking, cuando se definan transiciones posteriores.
6. Outbox y Analytics cuando exista mecanismo de entrega y recuperación verificable.
