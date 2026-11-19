# Catálogo completo de endpoints de FlashDelivery

Revisión: 2026-11-19. **40 operaciones de negocio/módulos y 3 sondas de infraestructura: 43 combinaciones método + ruta.** Basado en [OpenAPI](openapi.json), [registro de rutas](../../app/infra/routes.py), handlers y [stack](../../app/infra/stack.py). Este documento describe el contrato implementado; la evidencia de su verificación está en [validación](../validation.md).

## Cómo llamar a la API

- Aplicación local: `http://localhost:8080`; rutas de negocio bajo `/api/v1`. El proxy añade internamente la base de ejecución de API Gateway en MiniStack.
- Acceso directo al emulador: `http://127.0.0.1:4566/_aws/execute-api/<ApiId>/local` + ruta. ApiId está en `app/.local/outputs.json`; no es fijo.
- Sesión: `Authorization: Bearer <TOKEN>`. Cuerpos JSON: `Content-Type: application/json`.
- Público significa sin sesión Bearer. Seguimiento público sí exige su token de enlace como parámetro `{token}`; no es el mismo token de sesión.
- `Idempotency-Key` es obligatorio solo donde se indica. Mantenerlo al reintentar la misma intención; contenido distinto con la misma clave devuelve 409.
- Listados: `limit` 1–100, por defecto 25; `cursor` opaco de nextCursor. No reutilizarlo al cambiar actor/filtro/consulta. Final cuando nextCursor sea null.
- IDs: 1–128 caracteres ASCII alfanuméricos, guion o guion bajo. Fechas UTC. Los placeholders de ejemplos se sustituyen por valores reales; no contienen credenciales del entorno.

No hay endpoint DELETE para eliminar perfiles o pedidos de la base. Cancelar, fallar, suspender, dejar de compartir y revocar un enlace tienen efectos distintos. La limpieza de datos locales es mantenimiento explícito y no equivale a esos comandos.

## Inventario por módulo

| Módulo | Operaciones |
| --- | ---: |
| Bandejas y auditoría administrativa | 6 |
| Identidad | 2 |
| Comercios y zonas | 4 |
| Repartidores | 6 |
| Pedidos y consultas | 5 |
| Ciclo de entrega | 5 |
| Presencia | 3 |
| Seguimiento, ubicación y rutas | 8 |
| Estadísticas | 1 |
| Salud/readiness | 3 |
| **Total** | **43** |

## Bandejas y auditoría administrativa

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| GET | `/api/v1/admin/stores` | ADMIN | 200 |
| GET | `/api/v1/admin/couriers` | ADMIN | 200 |
| GET | `/api/v1/admin/stores/{storeId}` | ADMIN | 200 |
| GET | `/api/v1/admin/couriers/{courierId}` | ADMIN | 200 |
| GET | `/api/v1/admin/stores/{storeId}/events` | ADMIN | 200 |
| GET | `/api/v1/admin/couriers/{courierId}/events` | ADMIN | 200 |

### 01. GET /api/v1/admin/stores

Listar perfiles por estado (GSI2 eventual, relectura fuerte; solo ADMIN).

**Acceso:** ADMIN.

Filtro status: PENDING por defecto, ENABLED o SUSPENDED. GSI eventual con relectura fuerte. Página vacía puede tener nextCursor; ordenar por creación del perfil, no última decisión.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |
| `status` | query | No | ApprovalStatus; predeterminado PENDING |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; AdminProfilePage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 02. GET /api/v1/admin/couriers

Listar perfiles por estado (GSI2 eventual, relectura fuerte; solo ADMIN).

**Acceso:** ADMIN.

Filtro status: PENDING por defecto, ENABLED o SUSPENDED. GSI eventual con relectura fuerte. Página vacía puede tener nextCursor; ordenar por creación del perfil, no última decisión.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |
| `status` | query | No | ApprovalStatus; predeterminado PENDING |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; AdminProfilePage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 03. GET /api/v1/admin/stores/{storeId}

Consultar perfil actual; solo ADMIN.

**Acceso:** ADMIN.

Consulta el perfil actual por ID. No otorga acceso a GPS.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `storeId` | path | Sí | string |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; AdminProfile: `storeId`, `courierId`, `name`, `zoneId`, `enabled`, `available`, `approvalStatus`, `version`, `createdAt`, `updatedAt`, `activeOrderId` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 04. GET /api/v1/admin/couriers/{courierId}

Consultar perfil actual; solo ADMIN.

**Acceso:** ADMIN.

Consulta el perfil actual por ID. Incluye activeOrderId o null. No otorga acceso a GPS.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `courierId` | path | Sí | string |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; AdminProfile: `storeId`, `courierId`, `name`, `zoneId`, `enabled`, `available`, `approvalStatus`, `version`, `createdAt`, `updatedAt`, `activeOrderId` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 05. GET /api/v1/admin/stores/{storeId}/events

Consultar decisiones más recientes primero; solo ADMIN.

**Acceso:** ADMIN.

Auditoría descendente: actorId, fecha, motivo, fromStatus/toStatus y profileVersion. No reconstruye decisiones anteriores a esta función.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `storeId` | path | Sí | string |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; ProfileAuditPage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 06. GET /api/v1/admin/couriers/{courierId}/events

Consultar decisiones más recientes primero; solo ADMIN.

**Acceso:** ADMIN.

Auditoría descendente: actorId, fecha, motivo, fromStatus/toStatus y profileVersion. No reconstruye decisiones anteriores a esta función.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `courierId` | path | Sí | string |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; ProfileAuditPage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

## Identidad

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/dev-login` | Público; ADMIN exige adminCode | 200 |
| GET | `/api/v1/auth/me` | Cualquier sesión válida | 200 |

### 07. POST /api/v1/auth/dev-login

Inicio de sesión de desarrollo (solo local).

**Acceso:** Público; ADMIN exige adminCode.

No registra un perfil ni crea un usuario DynamoDB. Es autenticación de desarrollo; adminCode es obligatorio para ADMIN. El acceso administrativo depende de configuración local, no de un ítem ADMIN.

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `userId` | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `role` | Sí | string (STORE, COURIER, ADMIN) |
| `adminCode` | No | string; Obligatorio para ADMIN |

Ejemplo:

```json
{
  "userId": "admin",
  "role": "ADMIN",
  "adminCode": "<CODIGO_ADMIN_LOCAL>"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Token firmado; Session: `token`, `expiresAt`, `actor` |
| 400 | Error de dominio; Error |
| 403 | Error de dominio; Error |

### 08. GET /api/v1/auth/me

Actor de la sesión.

**Acceso:** Cualquier sesión válida.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Actor; Actor: `actorId`, `role` |
| 401 | Error de dominio; Error |

## Comercios y zonas

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| GET | `/api/v1/zones` | Público | 200 |
| POST | `/api/v1/stores` | STORE | 201 |
| GET | `/api/v1/stores/me` | STORE propio | 200 |
| PATCH | `/api/v1/admin/stores/{storeId}` | ADMIN | 200 |

### 09. GET /api/v1/zones

Catálogo de zonas predefinidas.

**Acceso:** Público.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Zonas; object: `items` |

### 10. POST /api/v1/stores

Registrar mi comercio (queda pendiente de habilitación).

**Acceso:** STORE.

Crea perfil PENDING, enabled=false. El ID se toma del actor, no del cuerpo. Repetir el alta devuelve 409.

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `name` | Sí | string; long. mín. 1; long. máx. 120 |
| `zoneId` | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

Ejemplo:

```json
{
  "name": "Perfil de ejemplo",
  "zoneId": "centro"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 201 | Comercio; Store: `storeId`, `name`, `zoneId`, `enabled`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 11. GET /api/v1/stores/me

Mi comercio.

**Acceso:** STORE propio.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Comercio; Store: `storeId`, `name`, `zoneId`, `enabled`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 12. PATCH /api/v1/admin/stores/{storeId}

Habilitar o deshabilitar un comercio (ADMIN).

**Acceso:** ADMIN.

enabled=true habilita/reactiva; false pasa a SUSPENDED. Perfil y auditoría se confirman juntos. expectedVersion y reason opcionales en API por compatibilidad, exigidos por la bandeja. No-op no duplica eventos. 409 PROFILE_CHANGED ante otro cambio con versión vieja.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `storeId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `enabled` | Sí | boolean |
| `expectedVersion` | No | integer; mín. 1; Versión leída; 409 si cambió. Misma decisión ya aplicada es no-op. |
| `reason` | No | string; long. mín. 1; long. máx. 300; Motivo; obligatorio en la interfaz. Clientes anteriores pueden omitirlo. |

Ejemplo:

```json
{
  "enabled": true,
  "expectedVersion": 1,
  "reason": "Perfil verificado"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Comercio; Store: `storeId`, `name`, `zoneId`, `enabled`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

## Repartidores

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| POST | `/api/v1/couriers` | COURIER | 201 |
| GET | `/api/v1/couriers/me` | COURIER propio | 200 |
| PATCH | `/api/v1/couriers/me/availability` | COURIER habilitado | 200 |
| GET | `/api/v1/couriers/me/active` | COURIER propio | 200 |
| GET | `/api/v1/couriers/me/orders` | COURIER propio | 200 |
| PATCH | `/api/v1/admin/couriers/{courierId}` | ADMIN | 200 |

### 13. POST /api/v1/couriers

Registrar mi perfil de repartidor (pendiente de habilitación).

**Acceso:** COURIER.

Crea perfil PENDING. No activa la disponibilidad ni concede habilitación administrativa.

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `name` | Sí | string; long. mín. 1; long. máx. 120 |
| `zoneId` | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

Ejemplo:

```json
{
  "name": "Perfil de ejemplo",
  "zoneId": "centro"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 201 | Repartidor; Courier: `courierId`, `name`, `zoneId`, `enabled`, `available`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 14. GET /api/v1/couriers/me

Mi perfil de repartidor.

**Acceso:** COURIER propio.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Repartidor; Courier: `courierId`, `name`, `zoneId`, `enabled`, `available`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 15. PATCH /api/v1/couriers/me/availability

Declarar disponibilidad (T6).

**Acceso:** COURIER habilitado.

available=false no cancela una entrega activa. Cambia disponibilidad y retira presencia cuando corresponde.

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `available` | Sí | boolean |

Ejemplo:

```json
{
  "available": true
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Repartidor; Courier: `courierId`, `name`, `zoneId`, `enabled`, `available`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 16. GET /api/v1/couriers/me/active

Mi pedido activo (lectura fuerte de COURIER#id / ACTIVE).

**Acceso:** COURIER propio.

Devuelve {"order":null} si no hay ACTIVE; de otro modo recupera el pedido mediante lectura fuerte.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido activo o null; object: `order` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |

### 17. GET /api/v1/couriers/me/orders

Mi historial (GSI1, más reciente primero).

**Acceso:** COURIER propio.

El historial conserva los pedidos terminados. Orden por fecha de creación del pedido, no de aceptación.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Página; OrderPage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |

### 18. PATCH /api/v1/admin/couriers/{courierId}

Habilitar o deshabilitar un repartidor (ADMIN).

**Acceso:** ADMIN.

enabled=true habilita/reactiva; false pasa a SUSPENDED. Perfil y auditoría se confirman juntos. expectedVersion y reason opcionales en API por compatibilidad, exigidos por la bandeja. No-op no duplica eventos. 409 PROFILE_CHANGED ante otro cambio con versión vieja. Suspender con ACTIVE devuelve 409 COURIER_HAS_ACTIVE_ORDER, sin cambios; al suspender available queda false.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `courierId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `enabled` | Sí | boolean |
| `expectedVersion` | No | integer; mín. 1; Versión leída; 409 si cambió. Misma decisión ya aplicada es no-op. |
| `reason` | No | string; long. mín. 1; long. máx. 300; Motivo; obligatorio en la interfaz. Clientes anteriores pueden omitirlo. |

Ejemplo:

```json
{
  "enabled": true,
  "expectedVersion": 1,
  "reason": "Perfil verificado"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Repartidor; Courier: `courierId`, `name`, `zoneId`, `enabled`, `available`, `createdAt`, `updatedAt`, `version`, `approvalStatus` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

## Pedidos y consultas

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| POST | `/api/v1/orders` | STORE habilitado | 201 |
| GET | `/api/v1/orders/available` | COURIER habilitado de la zona o ADMIN | 200 |
| GET | `/api/v1/orders/{orderId}` | STORE propietario, COURIER asignado o ADMIN | 200 |
| GET | `/api/v1/orders/{orderId}/events` | STORE propietario, COURIER asignado o ADMIN | 200 |
| GET | `/api/v1/stores/me/orders` | STORE propio | 200 |

### 19. POST /api/v1/orders

Crear pedido (T1). Devuelve el token de seguimiento.

**Acceso:** STORE habilitado.

Comercio habilitado. La zona sale del perfil. pickupLocation y dropoffLocation son opcionales pero deben enviarse juntos; no se infieren de direcciones. La creación devuelve trackingToken.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `pickupAddress` | Sí | string; long. mín. 1; long. máx. 300 |
| `dropoffAddress` | Sí | string; long. mín. 1; long. máx. 300 |
| `feeMinor` | Sí | integer; mín. 1; máx. 100000000; Tarifa en la unidad mínima (COP) |
| `pickupLocation` | No | OrderLocation |
| `dropoffLocation` | No | OrderLocation |

Ejemplo:

```json
{
  "pickupAddress": "Calle de recogida",
  "dropoffAddress": "Calle de entrega",
  "feeMinor": 8000
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 201 | Pedido creado (o resultado previo del mismo intento); CreatedOrder |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 20. GET /api/v1/orders/available

Pedidos abiertos de una zona (GSI2 disperso, más antiguo primero).

**Acceso:** COURIER habilitado de la zona o ADMIN.

zoneId obligatorio; solo PENDING. Índice eventual, más antiguos primero. Ver una oferta no garantiza ganarla.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `zoneId` | query | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Página sin direcciones de destino; OrderPage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |

### 21. GET /api/v1/orders/{orderId}

Detalle (comercio propietario, repartidor asignado o ADMIN).

**Acceso:** STORE propietario, COURIER asignado o ADMIN.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 401 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 22. GET /api/v1/orders/{orderId}/events

Historial de eventos del pedido.

**Acceso:** STORE propietario, COURIER asignado o ADMIN.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Página; EventPage: `items`, `nextCursor` |
| 401 | Error de dominio; Error |
| 404 | Error de dominio; Error |

### 23. GET /api/v1/stores/me/orders

Pedidos de mi comercio: todos por fecha (GSI1) o por estado (GSI2).

**Acceso:** STORE propio.

Sin status usa GSI1; con status usa GSI2. Más recientes primero y paginación por cursor.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `status` | query | No | Status |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Página; OrderPage: `items`, `nextCursor` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |

## Ciclo de entrega

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| POST | `/api/v1/orders/{orderId}/accept` | COURIER habilitado/disponible de la zona | 200 |
| POST | `/api/v1/orders/{orderId}/pickup` | COURIER asignado | 200 |
| POST | `/api/v1/orders/{orderId}/deliver` | COURIER asignado | 200 |
| POST | `/api/v1/orders/{orderId}/cancel` | STORE propietario | 200 |
| POST | `/api/v1/orders/{orderId}/fail` | ADMIN | 200 |

### 24. POST /api/v1/orders/{orderId}/accept

Aceptar pedido (T2): un solo ganador, los demás 409 ORDER_ALREADY_ASSIGNED.

**Acceso:** COURIER habilitado/disponible de la zona.

PENDING → ASSIGNED. Una transacción comprueba perfil, versión y ausencia de ACTIVE. Un ganador por pedido y una entrega activa por repartidor.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido tras la transición; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 25. POST /api/v1/orders/{orderId}/pickup

Marcar recogido (T3, repartidor asignado).

**Acceso:** COURIER asignado.

ASSIGNED → PICKED_UP. Solo el repartidor asignado; la llegada del marcador no ejecuta este comando.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido tras la transición; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 26. POST /api/v1/orders/{orderId}/deliver

Marcar entregado (T4): libera ACTIVE y suma la estadística una vez.

**Acceso:** COURIER asignado.

PICKED_UP → DELIVERED. Libera ACTIVE y suma una sola vez el agregado mensual dentro del mismo commit.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido tras la transición; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 27. POST /api/v1/orders/{orderId}/cancel

Cancelar (T5, comercio propietario, PENDING o ASSIGNED).

**Acceso:** STORE propietario.

Solo propietario, desde PENDING o ASSIGNED. Si estaba asignado, libera ACTIVE. No es cancelación normal después de recogida.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido tras la transición; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

### 28. POST /api/v1/orders/{orderId}/fail

Marcar fallido (procedimiento excepcional, ADMIN, desde PICKED_UP).

**Acceso:** ADMIN.

Solo ADMIN desde PICKED_UP. Procedimiento excepcional, libera ACTIVE; no cuenta como entrega exitosa.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `Idempotency-Key` | header | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Pedido tras la transición; Order: `orderId`, `storeId`, `zoneId`, `status`, `courierId`, `pickupAddress`, `dropoffAddress`, `feeMinor`, `currency`, `createdAt`, `updatedAt`, `version`, `pickupLocation`, `dropoffLocation` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |

## Presencia

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| POST | `/api/v1/couriers/me/heartbeat` | COURIER habilitado y disponible | 200 |
| DELETE | `/api/v1/couriers/me/heartbeat` | COURIER propio | 204 |
| GET | `/api/v1/zones/{zoneId}/couriers` | STORE de la zona o ADMIN | 200 |

### 29. POST /api/v1/couriers/me/heartbeat

Heartbeat: presencia efímera en Redis (TTL 60 s).

**Acceso:** COURIER habilitado y disponible.

Renueva heartbeat y ZSET, TTL inicial 60 s. Presencia no adjudica pedidos.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Presencia; Presence: `courierId`, `zoneId`, `lastHeartbeatEpoch`, `expiresInSeconds` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 30. DELETE /api/v1/couriers/me/heartbeat

Salir de la presencia de la zona.

**Acceso:** COURIER propio.

Retira heartbeat y miembro del ZSET. No cancela pedido ni sustituye el PATCH de disponibilidad.

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 204 | Sin contenido |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 31. GET /api/v1/zones/{zoneId}/couriers

Repartidores con heartbeat vigente en la zona (comercio de la zona o ADMIN).

**Acceso:** STORE de la zona o ADMIN.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `zoneId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Página; object: `items`, `nextCursor` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 503 | Error de dominio; Error |

## Seguimiento, ubicación y rutas

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| GET | `/api/v1/tracking/{token}` | Público con token válido | 200 |
| POST | `/api/v1/orders/{orderId}/location` | COURIER asignado, pedido activo | 202 |
| GET | `/api/v1/orders/{orderId}/location` | STORE propietario o COURIER asignado | 200 |
| DELETE | `/api/v1/orders/{orderId}/location` | COURIER asignado | 204 |
| GET | `/api/v1/tracking/{token}/location` | Público con token geográfico vigente | 200 |
| DELETE | `/api/v1/orders/{orderId}/tracking-token` | STORE propietario | 204 |
| GET | `/api/v1/orders/{orderId}/route` | STORE propietario o COURIER asignado | 200 |
| GET | `/api/v1/tracking/{token}/route` | Público con token geográfico vigente | 200 |

### 32. GET /api/v1/tracking/{token}

Seguimiento público por token: solo estado e hitos.

**Acceso:** Público con token válido.

Solo estado y eventos mínimos. Si existe TRACKING, su expiración/revocación también rechaza el enlace para estados; tokens históricos sin TRACKING conservan solo compatibilidad de estados.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `token` | path | Sí | string; long. máx. 257 |
| `limit` | query | No | integer; mín. 1; máx. 100; predeterminado 25 |
| `cursor` | query | No | string; long. máx. 8192 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Seguimiento; Tracking: `orderId`, `status`, `updatedAt`, `events`, `nextCursor` |
| 404 | Error de dominio; Error |

### 33. POST /api/v1/orders/{orderId}/location

Publicar última ubicación: solo repartidor asignado, ASSIGNED/PICKED_UP; mínimo 3 s.

**Acceso:** COURIER asignado, pedido activo.

Solo ASSIGNED/PICKED_UP y repartidor asignado. Control temporal/secuencia y frecuencia mínima 3 s, sin Idempotency-Key. SIMULATED exige configuración backend local. No guarda histórico GPS DynamoDB.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo JSON:**

| Campo | Obligatorio | Tipo / reglas |
| --- | --- | --- |
| `latitude` | Sí | number; mín. -90; máx. 90 |
| `longitude` | Sí | number; mín. -180; máx. 180 |
| `accuracyMeters` | No | number; mín. 0 |
| `recordedAt` | Sí | string [date-time]; UTC Z; edad máxima 120 s, futuro máximo 15 s |
| `source` | Sí | string (SIMULATED, BROWSER_GPS) |
| `sequence` | No | integer; mín. 0; máx. 9007199254740991 |
| `speedMps` | No | number; mín. 0; máx. 100 |
| `headingDegrees` | No | number; mín. 0; máx. 360; máximo excluido |

Ejemplo:

```json
{
  "latitude": 11.24424,
  "longitude": -74.21219,
  "recordedAt": "<FECHA_UTC_ACTUAL_Z>",
  "source": "BROWSER_GPS"
}
```

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 202 | Correcto; LocationAccepted: `orderId`, `recordedAt`, `accepted` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 34. GET /api/v1/orders/{orderId}/location

Ubicación del propietario/asignado: FRESH hasta 15 s, STALE hasta 120 s, luego UNAVAILABLE.

**Acceso:** STORE propietario o COURIER asignado.

ADMIN no puede leer geografía. Frescura inicial: FRESH hasta 15 s, STALE hasta 120 s y después UNAVAILABLE. Un estado terminal oculta la posición.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; LatestLocation: `orderId`, `status`, `updatedAt`, `location`, `freshness` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 35. DELETE /api/v1/orders/{orderId}/location

Dejar de compartir: repartidor asignado, elimina coordenadas efímeras.

**Acceso:** COURIER asignado.

Deja de compartir mediante marca temporal sin coordenadas y retira rutas; no modifica el estado del pedido.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 204 | Correcto |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 36. GET /api/v1/tracking/{token}/location

Ubicación pública mínima con token aleatorio válido, no revocado, menor a 24 h.

**Acceso:** Público con token geográfico vigente.

Credencial TRACKING vigente/no revocada y estado activo. No expone identidades ni direcciones.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `token` | path | Sí | string; long. máx. 257 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; LatestLocation: `orderId`, `status`, `updatedAt`, `location`, `freshness` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 37. DELETE /api/v1/orders/{orderId}/tracking-token

Revocar enlace público: solo comercio propietario; idempotente.

**Acceso:** STORE propietario.

Revocación persistente por comercio propietario; no borra pedido/eventos. El token no puede regenerarse por un endpoint de esta versión.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 204 | Correcto |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 38. GET /api/v1/orders/{orderId}/route

Ruta activa y ETA aproximada, perfil automóvil sin tráfico real. Sin posición devuelve puntos sin origen inventado.

**Acceso:** STORE propietario o COURIER asignado.

Ruta/ETA aproximada por fase mediante Redis/OSRM. ADMIN excluido. Sin puntos/posición puede devolver route=null; no cambia estados.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `orderId` | path | Sí | Id; patrón `^[A-Za-z0-9_-]{1,128}$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; OrderRoute: `orderId`, `status`, `route`, `points` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

### 39. GET /api/v1/tracking/{token}/route

Ruta activa y ETA aproximada, perfil automóvil sin tráfico real. Sin posición devuelve puntos sin origen inventado.

**Acceso:** Público con token geográfico vigente.

Mismos controles de credencial/estado de geografía pública, con DTO mínimo. No incluye anotaciones internas ni instrucciones privadas.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `token` | path | Sí | string; long. máx. 257 |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Correcto; OrderRoute: `orderId`, `status`, `route`, `points` |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |
| 404 | Error de dominio; Error |
| 409 | Error de dominio; Error |
| 422 | Error de dominio; Error |
| 429 | Error de dominio; Error |
| 503 | Error de dominio; Error |

## Estadísticas

| Método | Ruta | Acceso | Éxito |
| --- | --- | --- | --- |
| GET | `/api/v1/stores/me/stats` | STORE propio | 200 |

### 40. GET /api/v1/stores/me/stats

Estadística mensual de mi comercio (Cache-Aside Redis).

**Acceso:** STORE propio.

month obligatorio YYYY-MM. Devuelve agregado mensual y source cache/dynamodb. Cache-Aside, TTL inicial 300 s y fallback al origen ante fallo de caché.

**Parámetros:**

| Nombre | Ubicación | Obligatorio | Tipo / reglas |
| --- | --- | --- | --- |
| `month` | query | Sí | string; patrón `^[0-9]{4}-(0[1-9]|1[0-2])$` |

**Cuerpo:** no requiere JSON de entrada.

**Respuestas declaradas:**

| HTTP | Resultado |
| --- | --- |
| 200 | Agregado; Stats: `storeId`, `month`, `deliveredCount`, `totalFeeMinor`, `updatedAt`, `source` |
| 400 | Error de dominio; Error |
| 401 | Error de dominio; Error |
| 403 | Error de dominio; Error |

## Sondas de infraestructura (41–43)

| Nº | Método y ruta | Acceso | Resultado |
| --- | --- | --- | --- |
| 41 | `GET /health` | Público | 200: ejecución de Health sin dependencias |
| 42 | `GET /api/v1/health` | Público | Alias de la misma Lambda; 200 |
| 43 | `GET /api/v1/ready` | Público | 200 si DynamoDB/Redis responden; 503 en caso contrario |

Health devuelve `service`, `status`, `environment`. Readiness añade `checks.dynamodb` y `checks.redis`. No son pruebas de un recorrido OSRM, de IAM productivo ni de la demo GPS. Estas tres rutas se declaran en stack.py; no se duplican como operaciones de módulos en OpenAPI.

## Errores e interpretación

Formato común en módulos:

```json
{"error":{"code":"ORDER_ALREADY_ASSIGNED","message":"Otro repartidor ya aceptó este pedido","requestId":"identificador-de-trazabilidad"}}
```

| HTTP | Significado general |
| --- | --- |
| 400 | Cuerpo, parámetro, cursor o Idempotency-Key inválidos |
| 401 | Falta sesión o token de sesión inválido/expirado |
| 403 | Rol o habilitación insuficiente |
| 404 | Recurso inexistente/no visible o token público rechazado |
| 409 | Conflicto de versión, estado, intención o asignación |
| 429 | Frecuencia excedida |
| 500 | Error interno no expuesto al cliente |
| 503 | Dependencia no disponible |

Las tablas de cada operación reproducen los códigos declarados en OpenAPI; la capa HTTP también traduce errores comunes. Un timeout no prueba que no hubo commit. El replay conserva efectos, pero el servicio puede devolver el estado actual del pedido al reconstruir la respuesta.

## Secuencia de prueba sin geografía

1. POST dev-login por cada actor; registrar comercio y repartidor con sus tokens respectivos.
2. ADMIN lista/detalla los perfiles y los habilita con PATCH. El código administrativo permanece en la configuración local; no hay fila ADMIN que crear.
3. STORE crea un pedido con Idempotency-Key y sin coordenadas.
4. COURIER activa available, consulta ofertas de su zona y ejecuta accept con otra clave de intención.
5. El mismo COURIER ejecuta pickup y deliver, cada intención con su clave estable.
6. STORE consulta eventos y estadística del mes; el destinatario puede consultar estados mediante trackingToken.

Este documento también inventaría las rutas geográficas porque existen en el contrato. La demo GPS no se corrigió ni se presenta como validada en esta entrega.

## Schemas de referencia

Los schemas completos y requeridos están en [OpenAPI](openapi.json). Resumen para reconocer los principales DTOs:

| Schema | Finalidad |
| --- | --- |
| Session / Actor | Token y rol/identidad autenticada |
| Store / Courier | Perfil propio con habilitación, estado de aprobación y versión |
| AdminProfile / AdminProfilePage | Detalle/listado administrativo; activeOrderId en detalle de repartidor |
| ProfileAudit / ProfileAuditPage | Motivo, actor, fecha y transición de aprobación |
| Order / CreatedOrder / OrderPage | Pedido, creación con trackingToken y páginas de pedidos |
| EventPage / Tracking | Eventos privados y proyección pública de estados |
| LatestLocation / OrderRoute | Última muestra/frescura y geometría/progreso/ETA |
| Stats / Presence | Agregado mensual y presencia de zona |

Fuentes ejecutables: registro ROUTES, ROUTES de cada handler y stack. Prueba de contrato: `tests/test_api_contract.py`. El estado de la base local no modifica cuáles rutas existen.
