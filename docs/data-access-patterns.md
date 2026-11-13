> Documento histórico de fase 1. Para el diseño vigente consultar [arquitectura general](ARQUITECTURA_GENERAL.md) y [especificaciones](specs/README.md). Sus diferencias no deben trasladarse a código sin reconciliación.

# Patrones de acceso — diseño v1

Propuesta para implementación futura en `FlashDeliveryTable`, sin modificar todavía
recursos ni datos. Todos los atributos de claves son String. Los módulos son dueños
de sus ítems aunque compartan partición. No se usan Scan ni FilterExpression para
resolver búsquedas principales.

## Convenciones y registros

IDs opacos no contienen el separador `#`. Fechas de claves: UTC con ancho fijo,
por ejemplo `2026-11-10T21:15:05.000000Z`. Un ID como sufijo desempata fechas iguales.
`entity_type`, `schema_version` y `version` identifican y versionan los registros.
Las claves son responsabilidad de repositorios, no de consumidores de contratos.

| Ítem / dueño | PK | SK | GSI1PK / GSI1SK | GSI2PK / GSI2SK |
| --- | --- | --- | --- | --- |
| Perfil / Identity | USER#user_id | PROFILE | — | — |
| Comercio / Stores | STORE#store_id | PROFILE | — | — |
| Repartidor / Couriers | COURIER#courier_id | PROFILE | — | — |
| Pedido / Orders | ORDER#order_id | META | STORE#store_id / ORDER#created_at#order_id | OPEN#ZONE#zone_id / ORDER#created_at#order_id, solo OPEN |
| Asignación / Dispatch | ORDER#order_id | ASSIGNMENT | COURIER#courier_id / ASSIGNMENT#accepted_at#order_id | — |
| Última posición / Tracking | ORDER#order_id | TRACKING#LATEST | — | — |
| Resultado idempotente / módulo del comando | IDEMPOTENCY#actor_id | OP#operation#key_digest | — | — |
| Métrica diaria / Analytics | STORE#store_id | METRIC#date | — | — |

`key_digest` es un hash de la clave idempotente; la huella del contenido se almacena
separadamente. `operation` incluye nombre y versión (p. ej. orders.publish.v1).
Solo se indexan los tipos indicados. Un pedido ASSIGNED conserva el GSI1 del comercio
y elimina GSI2PK/GSI2SK para abandonar el índice disperso de ofertas abiertas.
La asignación no duplica el ítem META en el GSI1: tiene su propio prefijo y propietario.

No hay búsqueda global de usuarios, comercios o repartidores en esta propuesta.
Los perfiles se consultan por ID. Un listado por propietario requerirá un patrón
específico antes de añadirlo; no se resolverá recorriendo la tabla.

## Matriz de consultas

| Necesidad | Operación / condición | Consistencia |
| --- | --- | --- |
| Perfil por ID | GetItem con PK exacta y SK=PROFILE | Fuerte cuando valida actividad |
| Detalle de pedido | GetItem ORDER#id / META | Fuerte para decisiones y recuperación |
| Historial del comercio por fecha | Query GSI1: GSI1PK=STORE#id y begins_with(GSI1SK, ORDER#); ScanIndexForward=false | Eventual |
| Ofertas abiertas de una zona | Query GSI2: GSI2PK=OPEN#ZONE#id y begins_with(GSI2SK, ORDER#) | Eventual |
| Asignación de una entrega | GetItem ORDER#id / ASSIGNMENT | Fuerte para comprobar ganador |
| Asignaciones del repartidor | Query GSI1: GSI1PK=COURIER#id y begins_with(GSI1SK, ASSIGNMENT#) | Eventual |
| Resultado de un comando | GetItem IDEMPOTENCY#actor_id / OP#operation#key_digest | Fuerte |
| Última posición de entrega | GetItem ORDER#id / TRACKING#LATEST | Según frescura requerida |
| Métrica de comercio/día | GetItem STORE#id / METRIC#date | Proyección con retraso explícito |
| Métricas de un rango de días | Query base: PK=STORE#id y SK BETWEEN METRIC#inicio AND METRIC#fin | Proyección con retraso explícito |

Los listados devuelven `LastEvaluatedKey` como cursor opaco del contrato. Para rangos
ordenados se usarán límites de sort key con el formato anterior. No se exige orden
estable ante inserciones concurrentes entre páginas. Un GSI no soporta lecturas
fuertemente consistentes; se revalida META al aceptar. Véase la
[documentación de consistencia DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html).

## Escrituras atómicas previstas

Publicación: una transacción comprueba actividad/versión del comercio y crea META
OPEN y el resultado idempotente, ambos con condición de ausencia. El order_id se
genera una sola vez para el intento; un reintento recupera el resultado persistido.
Si posteriormente se activa outbox, su ítem se incorpora al mismo commit.

Aceptación: un único TransactWriteItems contiene:

1. ConditionCheck sobre perfil de repartidor habilitado y versión del snapshot.
2. Update de ORDER#id / META, condicionado a existencia, status=OPEN y versión
   esperada: escribe courier_id, accepted_at, incrementa version y elimina las claves GSI2.
3. Put de ORDER#id / ASSIGNMENT, condicionado a ausencia, con las claves GSI1 del repartidor.
4. Put del resultado idempotente, condicionado a ausencia, con huella y AssignmentView.

El campo courier_id del pedido y la asignación quedan confirmados juntos. Si dos
repartidores compiten, solo uno puede cumplir OPEN y ausencia de asignación. La
idempotencia se recupera mediante lectura fuerte tras conflictos o respuestas perdidas.
Las condiciones del ítem META pertenecen al Update; no se agrega un ConditionCheck
separado sobre ese mismo ítem, ya que DynamoDB lo prohíbe en la misma transacción.
La transacción también comprueba versiones de perfiles para cerrar la carrera con
una deshabilitación. Cada módulo construye su fragmento mediante los puertos internos
explicados en [contratos](module-contracts.md).

Atomicidad e idempotencia siguen el contrato de
[TransactWriteItems](https://docs.aws.amazon.com/amazondynamodb/latest/APIReference/API_TransactWriteItems.html).
El test actual comprueba commit/rollback del emulador; no reemplaza una prueba futura
de concurrencia y recuperación del caso de uso.

## Presencia en Redis

| Clave | Tipo | Propósito |
| --- | --- | --- |
| fd:presence:courier:id | String JSON con zone_id, last_seen y sesión | Heartbeat con TTL |
| fd:presence:zone:id | Sorted Set, miembro courier_id y score last_seen | Candidatos vigentes por zona |

Valores iniciales propuestos: heartbeat cada 15 segundos y vigencia de 60 segundos,
configurables cuando se implemente. El servidor fija last_seen; no confía en el reloj
del dispositivo. ZRANGEBYSCORE filtra por ventana vigente; no se interpreta la mera
pertenencia al conjunto como prueba de conexión. El índice por zona no expira miembros
individuales automáticamente: hay que eliminar scores antiguos y revalidar la clave
con TTL y su zona actual. Cambio de zona, renovación y salida usarán una operación
atómica Redis (Lua) para evitar sesiones cruzadas; esa compatibilidad se probará en
su fase. Ninguna operación Redis forma parte del commit DynamoDB.

## Límites y decisiones pendientes

- Un índice de ofertas por zona puede concentrar tráfico; se empezará sin sharding.
  Medir antes de dividir particiones y cambiar el contrato de paginación.
- No hay máximo de entregas activas por repartidor ni reasignación. Si se requiere,
  diseñar un guard persistente y sus transiciones antes de implementarlo.
- No hay historial de ubicaciones de alta frecuencia. Definir frecuencia, retención
  y patrones antes de añadir nuevos ítems; evitar crecimiento ilimitado de una entrega.
- La retención de idempotencia, eventos y métricas requiere una decisión explícita.
  No se habilita TTL ni se presupone que el emulador reproduce retrasos reales de índices.
- Outbox todavía no tiene formato de clave ni índice: necesita un patrón de consumo,
  recuperación y deduplicación antes de activarse. No añadir un barrido Scan periódico.
- Direcciones y ubicaciones requieren control de acceso y minimización. Los DTOs
  de listados y los eventos no transportan esos datos.
