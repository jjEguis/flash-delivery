# Contratos y dependencias entre módulos

Revisión: 2026-11-18, implementación hasta SPEC-10. Este documento describe código existente; sustituye la propuesta de fase 1, disponible en Git. [Arquitectura de estudio](ARQUITECTURA_GENERAL.md), [OpenAPI](api/openapi.json), [modelo](data-model/README.md).

## Convenciones reales

Las llamadas de aplicación son funciones Python síncronas. Cada handler expone `main(event, context)` usando `shared.http.router`. El router interpreta el evento HTTP API v2, verifica la sesión en rutas protegidas, construye Request y traduce excepciones de dominio a JSON/HTTP. Las rutas públicas explícitas no confían en un rol enviado por el cliente.

`identity.contracts.ActorContext` es una dataclass inmutable con actor_id y role. store_id/courier_id se derivan del actor según su rol. `authorize(actor, *roles)` valida acceso de aplicación. No hay un archivo contracts.py por módulo ni un contenedor de inyección global; la mayoría de servicios reciben adapter/cache explícitos y llaman funciones/repositorios concretos.

El esquema físico y su serialización son internos. Los DTOs HTTP excluyen PK/SK, claves GSI, hashes y detalles de infraestructura. Las fechas son UTC; las claves se construyen en `shared.storage`. Los listados HTTP usan items/nextCursor; `Repository` usa Page(items, next_cursor). Request.page solo procesa limit/cursor: el soporte de rangos de fecha del repositorio no constituye un parámetro público de todas las rutas.

## Propiedad y colaboración

| Módulo / código de entrada | Funciones y responsabilidad | Colaboración efectiva |
| --- | --- | --- |
| Identity / handler.py, contracts.py, tokens.py | dev_login, me, ActorContext, authorize; emitir/verificar sesión de desarrollo | Configuración y primitivas de validación; no tabla USER |
| Stores / service.py | register_store, get_my_store, set_store_enabled; zonas y nombre del perfil | StoresRepository; decisión administrativa delegada a Approvals |
| Couriers / service.py | register_courier, get_my_courier, set_availability, get_active_order, list_my_orders, set_courier_enabled | CouriersRepository; Orders para activo; Approvals para decisiones |
| Orders / service.py | create_order, get_order, list_store_orders, list_open_orders, list_events, build_transition | StoresRepository para elegibilidad; Tracking para credencial/puntos; shared.run_command |
| Dispatch / service.py | accept_order, pick_up_order, deliver_order, cancel_order, fail_order | build_transition/load_order de Orders; repositorios Couriers/Analytics; un commit común |
| Availability / service.py | heartbeat, leave, list_present, go_offline | Lecturas de perfil mediante servicios Stores/Couriers; Redis TTL/ZSET |
| Tracking / handler.py y auxiliares | Publicar/leer/parar ubicación, revocar token, seguimiento público, get_route | OrdersRepository, TrackingAccess, RedisLocationStore, proveedor OSRM |
| Analytics / service.py, repository.py | get_month_stats, invalidate_month; agregado mensual con build_increment | DynamoDB fuente oficial; Redis Cache-Aside; Dispatch compone incremento |
| Approvals / service.py | listing, detail, events, change | Repositorios Stores/Couriers; ApprovalsRepository para auditoría; guard ACTIVE |
| shared | HTTP, errores, reloj, ajustes, clientes, claves/modelo/repositorio/transacciones | Primitivas técnicas; no coordina reglas de asignación o aprobación |

Stores/Couriers siguen siendo las Lambdas de los PATCH administrativos por compatibilidad. Approvals expone seis GET y comparte la lógica de transición de perfil. Cada tipo de ítem se valida contra el conjunto permitido por su repositorio al construir Put; no es aislamiento IAM entre entidades de la tabla.

## Frontera de una transacción

Un constructor de repositorio como `build_put`, `build_eligible_condition`, `build_release_active` o `build_increment` devuelve una acción DynamoDB. **Construirla no escribe nada.** El caso de uso combina pares `(acción, error de condición)` y llama a commit/run_command. Así una operación de negocio no se divide en varios commits ocultos de módulos distintos.

`Orders.build_transition` devuelve nuevo META y acciones para META, evento y STORE_STATUS_VIEW. Dispatch agrega ACTIVE, vista de repartidor y agregado cuando corresponda. La versión esperada está en la misma acción que sustituye el ítem. No se añade ConditionCheck separado sobre ese mismo ítem.

`run_command` añade un IDEMPOTENCY al commit y consulta su resultado ante replay/conflicto. `commit` se usa para mutaciones sin ese registro, como alta de perfiles y aprobaciones. Ni Redis, OSRM ni una llamada HTTP de un proveedor forman parte del commit DynamoDB.

Esta es coordinación modular mediante implementaciones compartidas, no independencia estricta de repositorios. Una futura extracción de microservicios exigiría rediseñar esos límites y sus garantías. No está implementada una saga, outbox, bus de eventos ni consumidor Analytics asíncrono.

## DTOs y permisos principales

| Respuesta | Contenido | Límite |
| --- | --- | --- |
| Perfil propio | ID, nombre, zona, enabled, approvalStatus, fechas/version; available en repartidor | Nunca ownerId/claves físicas |
| Pedido resumido | ID, comercio/zona, estado/fechas/version; recogida/tarifa y courierId si están presentes en el ítem leído | No dirección de destino ni puntos geográficos |
| Detalle de pedido | Resumen + dirección de destino y pickupLocation/dropoffLocation si existen | Comercio propietario, repartidor asignado o ADMIN |
| Historial repartidor | Campos de su vista: orderId/storeId/courierId/estado/fechas/version | No copia direcciones o tarifa desde otro ítem |
| Seguimiento público | orderId, status, updatedAt, eventos mínimos, nextCursor | Token validado; sin identidades/direcciones |
| Última ubicación | Estado, updatedAt, location o null, frescura | Propietario/asignado o token geográfico válido; ADMIN excluido |
| Ruta pública | Geometría/progreso/distancia/ETA/fase/versiones públicas | Sin identidades, direcciones ni anotaciones internas |
| Perfil administrativo | Datos mínimos de perfil; activeOrderId en detalle de repartidor | Solo ADMIN; el listado no expone GPS |
| Auditoría de perfil | actorId, occurredAt, fromStatus/toStatus, reason, profileVersion e IDs del evento/perfil | Solo ADMIN; no reconstrucción retroactiva |
| Estadística | Comercio/mes, entregas, importe, updatedAt y source | STORE propio; source indica cache o dynamodb |

El detalle exacto de campos requeridos/opcionales está en OpenAPI; las vistas de índices no tienen necesariamente los mismos atributos que META. Una proyección ALL no autoriza devolver todo el ítem.

## Reintentos y errores

- Comandos Orders/Dispatch: Idempotency-Key estable; misma huella recupera operación, otro contenido devuelve 409 IDEMPOTENCY_CONFLICT.
- Perfil/disponibilidad: sin clave idempotente obligatoria; escritura condicional/naturaleza repetible. PATCH administrativo acepta expectedVersion/reason opcionales por compatibilidad; la bandeja los exige.
- Misma decisión administrativa ya aplicada: no-op incluso si la versión del cliente es antigua; otro cambio con versión antigua: 409 PROFILE_CHANGED.
- Suspensión de repartidor con ACTIVE: 409 COURIER_HAS_ACTIVE_ORDER, sin modificación de perfil ni evento.
- Ubicación: control de timestamp/secuencia y frecuencia en Lua; no crea IDEMPOTENCY por cada muestra.
- Error técnico: el cliente no debe interpretar un timeout como ausencia de commit. Los logs/errores contienen requestId; no deben revelar credenciales/direcciones/coordenadas.

Las claves de intención pendientes se conservan en frontend para recuperación al reenviar; no existe reenvío offline automático. Los servicios reconstruyen algunas respuestas con lectura actual del pedido: idempotencia no garantiza un JSON congelado de su estado inicial.

## Puertos realmente utilizados y pruebas

Tracking declara protocolos para la lectura de pedidos y almacenamiento de la última ubicación; RedisLocationStore y el proveedor de rutas son adaptadores concretos reemplazables en pruebas. shared.DynamoDBAdapter acepta un cliente inyectado. El reloj e IDs pueden sustituirse mediante fixtures/monkeypatch.

Los fixtures comunes moto/fakeredis prueban servicios sin red; tests de contrato comparan OpenAPI, registro de rutas y handlers. Las integraciones prueban el paquete desplegado y conservan los escenarios reales de concurrencia. No se acredita una política universal de imports solo por llamar a esta arquitectura «hexagonal»; el límite concreto se comprueba leyendo estas colaboraciones.
