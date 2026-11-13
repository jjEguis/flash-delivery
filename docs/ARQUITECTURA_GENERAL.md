# FlashDelivery — Documento general de arquitectura

**Organización:** documento de arquitectura de referencia; especificaciones en [specs/README.md](specs/README.md). Estado real y secuencia en [PLAN_DE_TRABAJO.md](PLAN_DE_TRABAJO.md).

**Versión:** 1.1 · **Estado:** propuesta base para implementación · **Fecha:** 2026-11-12

## 1. Propósito y alcance

FlashDelivery coordina entregas de última milla. Un comercio crea una solicitud; los repartidores habilitados y disponibles de la zona la visualizan y compiten por aceptarla. La aceptación se confirma de manera atómica y solo puede ganar un repartidor. El destinatario consulta el estado mediante un token de seguimiento.

**MVP:** alta y habilitación de comercios/repartidores; disponibilidad y heartbeat; creación, consulta, aceptación, recogida, entrega y cancelación de pedidos; seguimiento; métricas básicas. **No incluye:** pagos, marketplace, mapas/GPS en tiempo real, optimización de rutas, múltiples pedidos activos por repartidor, notificaciones push.

**Decisión vigente:** desarrollar, ejecutar y probar únicamente con **MiniStack** y Redis local. Despliegue en AWS real es una intención futura, **no forma parte de esta fase**. La compatibilidad de MiniStack con API Gateway, Lambda, DynamoDB, GSI, TransactWriteItems y CDK debe validarse mediante una prueba de capacidad antes de depender de ella. No asumir equivalencia con LocalStack.

## 2. Arquitectura elegida y justificación

**Monolito modular serverless + arquitectura hexagonal ligera (puertos y adaptadores) + casos de uso.** Una base de código Python, con módulos lógicos independientes y funciones Lambda como adaptadores de entrada. API Gateway expone HTTP; DynamoDB persiste el estado oficial; Redis conserva presencia efímera y cachés. No hay llamadas Lambda-a-Lambda para ejecutar una transacción.

```text
React/Vite (posterior)
      │ HTTPS/JSON
      ▼
API Gateway [MiniStack, sujeto a verificación]
      │
      ▼
Lambda Python: handlers delgados
      │
      ▼
Casos de uso / servicios de aplicación
      ├── Identity, Stores, Couriers, Orders
      ├── Dispatch, Availability, Tracking, Analytics
      └── Puertos de persistencia, reloj, autenticación
                │
        Adaptadores compartidos
          ├── DynamoDB: FlashDeliveryTable (PK/SK, GSI1, GSI2)
          └── Redis: presencia, caché, rate limits
```

**Por qué:** permite demostrar Single Table Design, transacciones y caché con límites claros, despliegue local reproducible y menor complejidad que microservicios. La independencia es **lógica**, no de bases de datos: una única tabla compartida permite transacciones atómicas multi-entidad.

## 3. Principios obligatorios

1. Cada módulo expone **servicios de aplicación y DTOs**; ningún módulo importa repositorios internos de otro.
2. Los handlers solo validan HTTP, obtienen identidad autenticada, invocan un caso de uso y traducen errores.
3. **DynamoDB es fuente de verdad** para pedidos, asignación, estado habilitado y disponibilidad declarada; Redis nunca adjudica pedidos.
4. Toda mutación de estado de pedido escribe su evento de auditoría y mantiene las proyecciones requeridas de forma atómica.
5. Los GSI son eventualmente consistentes; la confirmación de aceptación consulta condiciones en los ítems base de DynamoDB.
6. Una sola entrega activa por repartidor; la existencia de `COURIER#id / ACTIVE` impide una segunda.
7. Zona **predefinida** (`zoneId`), sin geolocalización en el MVP.
8. Estadísticas básicas por comercio y mes; métricas avanzadas quedan para otra iteración.
9. IDs ULID/UUID, timestamps ISO 8601 UTC, montos en enteros de la unidad monetaria mínima, paginación por cursor.
10. Ningún módulo crea tablas DynamoDB adicionales; las proyecciones son ítems de la tabla única.

## 4. Módulos y propiedad

| Módulo | Responsable de | Expone | Consume |
|---|---|---|---|
| Identity | Principal, rol y autorización | `require_actor`, `authorize` | configuración de identidad |
| Stores | Perfil/habilitación de comercio | `get_store`, `assert_store_enabled` | Identity |
| Couriers | Perfil, zona, habilitación, disponibilidad declarada | `get_courier`, `assert_eligible` | Identity |
| Orders | Crear/leer pedido, estado y eventos | `create_order`, `get_order`, `list_store_orders` | Stores, Identity |
| Dispatch | Aceptación y transiciones críticas | `accept_order`, `mark_picked_up`, `mark_delivered`, `cancel_order` | Orders, Couriers, Identity, contrato transaccional |
| Availability | Heartbeat y candidatos efímeros | `heartbeat`, `list_present_couriers` | Couriers, Redis |
| Tracking | Vista pública limitada | `get_tracking` | Orders |
| Analytics | Agregados de entregas | `get_store_month_stats` | Orders, proyecciones |

**Regla de coordinación:** Dispatch es dueño del caso de uso `accept_order` y del ensamblado de su transacción, pero no debe acceder directamente a repositorios privados. Los módulos propietarios proporcionan **constructores de operaciones transaccionales** (`TransactWrite` descriptors) o puertos explícitos que Dispatch compone en una única llamada DynamoDB. Los contratos se fijan en SPEC-03 en `docs/specs/` (contratos pendientes de concretar) y deben versionarse.

## 5. Casos de uso MVP

CU01 registrar/habilitar comercio; CU02 registrar/habilitar repartidor; CU03 crear pedido; CU04 listar pedidos de comercio; CU05 cancelar pedido elegible; CU06 cambiar disponibilidad; CU07 listar pedidos abiertos de zona; CU08 aceptar pedido; CU09 ver pedido activo/historial; CU10 recoger y entregar; CU11 seguimiento por token; CU12 métricas mensuales básicas.

**Estados:** `PENDING -> ASSIGNED -> PICKED_UP -> DELIVERED`; `CANCELLED` desde `PENDING` o `ASSIGNED`; `FAILED` desde `PICKED_UP` únicamente por procedimiento excepcional autorizado. Las transiciones son validadas por estado actual, actor y versión.

## 6. Single Table Design — modelo canónico

Tabla `FlashDeliveryTable`: `PK` (String), `SK` (String). GSI1: `GSI1PK`, `GSI1SK` (String). GSI2: `GSI2PK`, `GSI2SK` (String). Los índices son dispersos: solo participan ítems con ambos atributos del índice.

| PK | SK | Tipo | Índices |
|---|---|---|---|
| `STORE#S01` | `PROFILE` | STORE | ninguno |
| `COURIER#R01` | `PROFILE` | COURIER | ninguno |
| `COURIER#R01` | `ACTIVE` | ACTIVE_ASSIGNMENT | ninguno |
| `ORDER#O01` | `META` | ORDER | GSI1 historial comercio; GSI2 abiertos si PENDING |
| `ORDER#O01` | `EVENT#<timestamp>#<id>` | ORDER_EVENT | ninguno |
| `COURIER#R01` | `ORDER#O01` | COURIER_ORDER_VIEW | GSI1 historial repartidor |
| `STORE#S01` | `STATUS#O01` | STORE_STATUS_VIEW | GSI2 estado comercio |
| `STORE#S01` | `STATS#YYYY-MM` | STORE_STATS | ninguno |
| `REQUEST#<scope>#<requestId>` | `IDEMPOTENCY` | IDEMPOTENCY | ninguno |

- GSI1 para ORDER: `STORE#S01 / ORDER#<createdAt>#O01`; para COURIER_ORDER_VIEW: `COURIER#R01 / ORDER#<createdAt>#O01`.
- GSI2 para ORDER PENDING: `ZONE#Z01#OPEN / CREATED#<createdAt>#O01`; retirar ambos atributos al asignar/cancelar.
- GSI2 para STORE_STATUS_VIEW: `STORE#S01#<status> / CREATED#<createdAt>#O01`.
- `ORDER/META` guarda `storeId`, `courierId`, `zoneId`, `status`, `createdAt`, `updatedAt`, `version`, direcciones, tarifa y `trackingTokenHash` (no exponer token sin procesar).
- Un `GetItem` o `Query` por clave reemplaza escaneos. Consultas con estado y fecha requieren usar GSI2; todos los estados por fecha usan GSI1.
- El acceso al pedido activo es lectura fuertemente consistente de `COURIER#id / ACTIVE` en tabla base.

**Nota de consistencia:** al usar dos proyecciones en ítems separados se acepta duplicación controlada. Las mutaciones deben mantenerlas dentro de la misma transacción. La lectura de GSI puede presentar retraso temporal.

## 7. Operaciones transaccionales

**T1 crear:** `ConditionCheck` comercio habilitado; `Put` ORDER/META si no existe; `Put` evento CREATED; `Put` STORE_STATUS_VIEW; `Put` registro de idempotencia. El `ConditionCheck` no puede referirse al mismo ítem que otra acción en esa transacción.

**T2 aceptar (crítica):** `ConditionCheck` COURIER/PROFILE (`enabled=true`, `available=true`, zona coincidente); `Update` ORDER/META si `status=PENDING AND attribute_not_exists(courierId)`; establecer `ASSIGNED`, `courierId`, versión y retirar GSI2 de zona; `Put` COURIER/ACTIVE si no existe; `Put` evento ASSIGNED; `Put` COURIER_ORDER_VIEW; `Update` STORE_STATUS_VIEW para estado ASSIGNED; `Put` registro idempotente. Si otra aceptación gana, devolver **409**. La comprobación de presencia reciente en Redis puede usarse como filtro adicional, pero no reemplaza las condiciones en DynamoDB.

**T3 recoger:** `Update` ORDER condicionado a `ASSIGNED`, courierId del actor; `Put` evento PICKED_UP; `Update` proyecciones.

**T4 entregar:** `Update` ORDER condicionado a `PICKED_UP` y actor asignado; `Put` evento DELIVERED; `Delete` ACTIVE con condición `orderId` esperado; `Update` vistas y agregado mensual. La actualización de agregados debe ser idempotente para no contar dos veces un reintento.

**T5 cancelar:** permitido para comercio propietario en PENDING/ASSIGNED; `Update` ORDER, evento CANCELLED, vista, retirar GSI2 abierto y `Delete` ACTIVE solo si había asignación; condiciones de pertenencia y estado. No permitir cancelación normal tras PICKED_UP.

**T6 disponibilidad declarada:** actualización condicional de COURIER/PROFILE; para pasar a no disponible puede haber ACTIVE, pero eso no cancela su pedido activo. Al finalizar, no vuelve a aparecer como disponible hasta activar su disponibilidad y renovar heartbeat.

**Idempotencia:** `requestId` estable por intención, clave acotada por actor/operación; registrar resultado de forma atómica. Reintentos con mismo requestId devuelven el resultado almacenado; requestId reutilizado con otro payload devuelve 409. `ClientRequestToken` solo complementa la idempotencia duradera. Nunca ejecutar dos acciones sobre el mismo ítem en una sola transacción. Considerar límites de transacciones de DynamoDB y de tamaño de ítem.

## 8. Redis y fallos

- `couriers:available:<zoneId>`: ZSET con score `lastHeartbeatEpoch`.
- `courier:heartbeat:<courierId>`: TTL; candidatos caducados se filtran.
- `cache:store:<storeId>:stats:<month>`: Cache-Aside con TTL.
- `cache:order:<orderId>`: opcional, TTL corto e invalidación poscommit.
- `ratelimit:<actor>:<route>`: contador con expiración.

Redis es una proyección reconstruible. Después del commit de DynamoDB, invalidar o actualizar Redis. Si falla, registrar y reconciliar; jamás revertir una asignación exitosa por fallo de caché. En caso de Redis caído, los endpoints dependientes de presencia pueden responder 503, pero las operaciones oficiales siguen protegidas por DynamoDB.

## 9. API, seguridad y errores

HTTP JSON, prefijo `/api/v1`; contratos completos en el OpenAPI pendiente de concretar en SPEC-03. Roles ADMIN, STORE, COURIER. Los IDs del actor provienen de contexto autenticado, nunca de parámetros no confiables. Validar pertenencia de comercio, zona, estado y propiedad de pedido. Seguimiento público con token aleatorio de alta entropía y respuesta mínima, sin datos sensibles innecesarios. Errores uniformes: `{ "error": { "code": "ORDER_ALREADY_ASSIGNED", "message": "...", "requestId": "..." } }`; HTTP 400/401/403/404/409/429/500/503.

**Autenticación local:** definir en SPEC-03 un adaptador de identidad de desarrollo, explícitamente no apto para producción; nunca confiar en un header de rol arbitrario fuera del entorno local.

## 10. Estructura del repositorio

```text
flash-delivery/
├── app/
│   ├── cdk.json
│   ├── requirements.txt / requirements.lock
│   ├── infra/{app.py,stack.py}
│   ├── layers/dependencias/{requirements.txt,requirements.lock}
│   ├── lambdas/
│   │   ├── health/handler.py
│   │   ├── readiness/handler.py
│   │   ├── {identity,stores,couriers,orders,dispatch,availability,tracking,analytics}/
│   │   └── shared/               # primitivas, configuración, adaptadores y caché
│   ├── tests/                    # unitarios moto/fakeredis
│   │   └── integration/          # MiniStack y Redis reales
│   └── scripts/                  # paquete, provisionamiento y persistencia
├── docs/
│   └── specs/
├── frontend/                     # posterior
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

Estructura alineada con el ejemplo del curso por instrucción del usuario. Los handlers de cada funcionalidad exponen `main(event, context)`; casos de uso y repositorios se incorporarán dentro de su módulo cuando se implementen. Evitar carpetas vacías y capas artificiales: generar cada subcarpeta cuando tenga código real. `shared` contiene únicamente primitivas transversales, nunca lógica de negocio.

## 11. MiniStack: estrategia de validación y despliegue local

1. Identificar **producto, versión e imagen** concretos de MiniStack y revisar documentación oficial disponible.
2. Ejecutar prueba de capacidades: DynamoDB tabla + GSI + consulta + `TransactWriteItems`; API Gateway -> Lambda; persistencia y reinicio.
3. Si CDK no despliega directamente sobre MiniStack, definir bootstrap local idempotente compatible y conservar IaC declarativa donde sea viable; documentar la diferencia sin fingir paridad.
4. Docker Compose levanta MiniStack y Redis con healthchecks y volúmenes; variables locales aisladas; no conectar a AWS real.
5. Endpoint `/api/v1/health` verificable; pruebas con pytest; scripts `up`, `bootstrap`, `test`, `down`.

**Puerta de calidad G0:** no comenzar Dispatch hasta verificar soporte real de transacciones y condiciones de DynamoDB. Si MiniStack no lo soporta, registrar bloqueo y decidir adaptación explícita con el equipo, sin sustituir silenciosamente el motor.

## 12. Calidad, observabilidad y pruebas

Pruebas unitarias por caso de uso; integración DynamoDB/Redis; contratos HTTP; concurrencia con 100 aceptaciones simultáneas (una ganadora); invariantes de ACTIVE y proyecciones; idempotencia; TTL y Redis caído; paginación. Logs estructurados con `requestId`, `orderId`, `actorId` y duración, sin direcciones ni tokens completos. Medir p50/p95, aciertos de caché, consultas e ítems leídos; usar 10k/100k pedidos como carga posterior, sin suponer superioridad de NoSQL frente a SQL.

## 13. Decisiones registradas (ADR)

| ADR | Decisión | Estado |
|---|---|---|
| ADR-001 | Monolito modular serverless con puertos/adaptadores | Aprobada |
| ADR-002 | DynamoDB única tabla + dos GSIs | Aprobada |
| ADR-003 | Redis derivado, DynamoDB autoridad | Aprobada |
| ADR-004 | Aceptación competitiva mediante transacción condicional | Aprobada |
| ADR-005 | MiniStack local exclusivamente en fase actual | Aprobada |
| ADR-006 | Zonas predefinidas y métricas básicas en MVP | Propuesta para validar |
| ADR-007 | Adaptador de identidad local temporal | Pendiente de definir |

## 14. Plan de especificaciones y secuencia

- **SPEC-00:** validar MiniStack, Docker Compose, conectividad y operaciones soportadas.
- **SPEC-01:** fijar esquema exacto de ítems, GSIs, consultas y proyecciones.
- **SPEC-02:** fijar invariantes, transacciones, idempotencia y conflictos.
- **SPEC-03:** fijar contratos de módulos, DTOs, API y autorización.
- **SPEC-04:** implementar vertical inicial Stores/Couriers/Orders.
- **SPEC-05:** implementar Dispatch/Availability/Tracking/Analytics.
- **SPEC-06:** pruebas de carga, concurrencia y evidencias de sustentación.

Cada SPEC debe aprobarse con pruebas y criterios de aceptación antes de iniciar la siguiente. Los documentos `modulos/*.pln` y `contratos/*` son borradores heredados de v1.0: **la presente arquitectura es la fuente de decisiones y los contratos deben alinearse antes de codificar**.

## 15. Riesgos y pendientes

- Compatibilidad real de MiniStack y de CDK con servicios necesarios (bloqueante).
- Coste de mantener proyecciones sincronizadas y restricciones de transacciones.
- Consistencia eventual de GSIs y latencia en listas de abiertos.
- Definir timeout de heartbeat, expiración de idempotencia y política de `FAILED`.
- Definir identidad local y políticas de seguridad sin credenciales de producción.
- Eventual despliegue AWS real: fase separada, no presupuestada ni implementada ahora.
