# SPEC-08 — Geolocalización y seguimiento de entregas

**Proyecto:** FlashDelivery  
**Estado:** Implementada (GEO-00 a GEO-05), pendiente revisión del PR  
**Prioridad:** Opcional después del flujo de entregas  
**Entorno actual:** MiniStack + Redis en Docker  
**Arquitectura:** Monolito modular serverless (Python, Lambda, API Gateway, DynamoDB Single Table Design)

Implementación y límites en [guía GEO](../geo/README.md); verificación previa en [GEO-00](../geo/GEO-00.md), resultados en [validación](../validation.md). Las coordenadas permanecen en Redis; los tokens nuevos incorporan credencial revocable sin índices en la tabla existente. La aplicación funcional :8080 utiliza el diseño unificado de FE-01 en todas sus vistas; el prototipo queda como referencia visual. Los mapas forman parte de su navegación. [Unificación](../frontend/UNIFICACION.md).

## 1. Decisión arquitectónica

Implementar seguimiento geográfico **solo durante entregas activas**, con dos fuentes intercambiables: `SIMULATED` (por defecto para desarrollo y demostración) y `BROWSER_GPS` (optativa, con consentimiento del repartidor). No es necesario contar con un vehículo físico. No convertir el backend en un proceso persistente: las actualizaciones entran por HTTP y las consultas leen Redis/DynamoDB.

**Condición de inicio:** implementar después de que Orders, Dispatch, Tracking y autenticación funcionen. No bloquear el MVP por esta característica.

## 2. Objetivos y exclusiones

### Objetivos
- Mostrar en un mapa la última ubicación conocida del repartidor asignado, durante `ASSIGNED` y `PICKED_UP`.
- Simular un recorrido reproducible entre puntos de prueba, con pausa, reanudación y finalización.
- Permitir GPS del navegador solo tras permiso explícito.
- Proteger el acceso: comercio propietario, repartidor asignado y destinatario con token de seguimiento válido.
- Mantener intacta la asignación por aceptación y las transacciones existentes.

### Fuera de alcance
- Optimización de rutas, cálculo de ETA fiable, navegación giro a giro, seguimiento en segundo plano con navegador cerrado, geocercas, histórico exhaustivo de coordenadas, facturación por distancia y WebSockets.

## 3. Componentes y límites de módulo

- **Frontend / Courier:** obtiene coordenadas con `navigator.geolocation.watchPosition` cuando el usuario lo habilita; detiene el seguimiento al finalizar/cancelar o cerrar sesión. En simulación genera puntos de una ruta de prueba. No accede directamente a Redis ni DynamoDB.
- **Tracking:** propietario de `POST location` y `GET latest location`; valida permisos, estados, frescura y coordenadas; usa puertos `LocationStore` y `OrderReader`.
- **Orders:** fuente de verdad del estado de la entrega y relación con comercio y repartidor.
- **Dispatch:** asignación transaccional; no modifica posiciones.
- **Redis:** última posición efímera por pedido con TTL.
- **DynamoDB:** estado oficial de la entrega y eventos de cambio de estado. No escribir cada muestra GPS en la tabla principal en esta fase.
- **Map UI:** Leaflet con OpenStreetMap u otro proveedor de tiles cuya política de uso se respete; indicar atribución.

## 4. Contratos HTTP propuestos (versionables)

Los nombres de rutas son una **propuesta nueva** y deben alinearse con el OpenAPI existente antes de implementar.

### `POST /orders/{orderId}/location`

**Autorización:** únicamente el repartidor actualmente asignado, con entrega en `ASSIGNED` o `PICKED_UP`.

```json
{
  "latitude": 11.2408,
  "longitude": -74.1990,
  "accuracyMeters": 12.5,
  "recordedAt": "2026-11-15T23:00:00Z",
  "source": "SIMULATED"
}
```

Validar: `latitude` entre -90 y 90, `longitude` entre -180 y 180, precisión no negativa si se envía, timestamp UTC no excesivamente antiguo/futuro y fuente permitida. Ignorar un punto más antiguo que el último aceptado. Identidad del repartidor proviene de la autenticación, nunca del cuerpo.

**Respuesta:** `202 Accepted` con `orderId`, `recordedAt` y `accepted: true`; `401/403` por acceso, `404` por pedido inexistente, `409` si no está activo, `422` por coordenadas inválidas, `429` por exceso de frecuencia.

### `GET /orders/{orderId}/location`

**Autorización:** comercio propietario o repartidor asignado. La vista pública debe utilizar un endpoint específico con token limitado y no reutilizar permisos internos.

```json
{
  "orderId": "O01",
  "location": {
    "latitude": 11.2408,
    "longitude": -74.1990,
    "accuracyMeters": 12.5,
    "recordedAt": "2026-11-15T23:00:00Z",
    "source": "SIMULATED"
  },
  "freshness": "FRESH"
}
```

Si no hay posición, responder `location: null` y `freshness: "UNAVAILABLE"`; nunca inventar coordenadas. Para muestras antiguas, `STALE` y hora de actualización visible.

### `GET /tracking/{token}/location`

Devuelve solo los datos mínimos para el destinatario, si el token es válido y la entrega permite seguimiento. No devolver identidad personal, teléfono, historial completo ni datos de otros pedidos. El token debe ser aleatorio, no derivado de `orderId`, almacenado de forma segura, revocable y con expiración.

## 5. Modelo Redis

Clave: `tracking:order:{orderId}:latest`  
Tipo: String JSON con `latitude`, `longitude`, `accuracyMeters`, `recordedAt`, `source`, `courierId` (interno)  
TTL inicial sugerido: **120 segundos**, configurable.

Una actualización debe ser atómica y rechazar marcas temporales anteriores (script Lua o mecanismo equivalente compatible con el Redis elegido). Redis no autoriza el acceso; la Lambda valida permisos y estado oficial antes de escribir. Limitar frecuencia por repartidor y pedido. Si Redis falla, no cambiar estados oficiales ni inventar seguimiento.

## 6. Single Table Design

No crear nuevas tablas ni GSIs para esta fase. Se reutiliza `ORDER#id / META` para verificar el estado y el repartidor asignado. Los eventos de estado permanecen en DynamoDB. No se persiste un evento por cada posición para evitar escrituras innecesarias. Si se solicita auditoría de trayectorias, diseñarla en una especificación posterior con política de retención.

## 7. Simulador de recorridos

- Incluir al menos una ruta ficticia definida como una secuencia de coordenadas de prueba (sin afirmar que corresponde a una ruta real de calles).
- Controles visibles en desarrollo: iniciar, pausar, reanudar, reiniciar y detener.
- Emitir una posición cada 3–5 segundos (configurable), a través del mismo contrato HTTP que el GPS real.
- No permitir iniciar si el usuario no es el repartidor asignado a una entrega activa.
- Señalizar claramente `Modo simulación` en todos los mapas y nunca representar posiciones simuladas como reales.
- Mantener los controles de simulación fuera de la interfaz de producción.

## 8. Interfaz y UX

- Seguir `SPEC-07_FRONTEND_DESIGN_v2.1.md`, con tema claro/oscuro y responsive.
- **Comercio:** tarjeta de seguimiento con mapa, estado, hora de última posición y aviso de datos obsoletos.
- **Repartidor:** interruptor explícito para compartir ubicación, estado del permiso, indicador de envío y botón de detener; simulador solo en desarrollo.
- **Destinatario:** mapa simple con marcador y texto de estado; no mostrar una ETA inventada.
- Si el navegador deniega el permiso, ofrecer seguimiento por estados sin bloquear la entrega.
- La API de geolocalización del navegador requiere un contexto seguro (HTTPS o localhost en navegadores compatibles).
- El mapa debe tener estados de carga, error y sin posición, además de alternativas textuales accesibles.

## 9. Compatibilidad MiniStack y ejecución

Antes de escribir código, comprobar qué operaciones API Gateway/Lambda/DynamoDB están soportadas por la versión concreta de MiniStack instalada. Redis se ejecuta en Docker independiente. No sustituir MiniStack por otro emulador sin aprobación. Documentar las pruebas de integración reales y las limitaciones observadas.

## 10. Seguridad y privacidad

- Solicitar consentimiento de ubicación al repartidor y compartir solo durante una entrega activa.
- Detener y borrar la ubicación efímera al completar o cancelar; manejar fallos de limpieza con TTL.
- No exponer coordenadas a comercios ajenos ni a destinatarios sin token válido.
- Evitar logs con coordenadas exactas o tokens.
- Aplicar límites de frecuencia y validación de payload.
- No almacenar ubicaciones permanentemente por defecto.

## 11. Pruebas y criterios de aceptación

1. Un repartidor asignado puede publicar ubicación válida para su pedido activo.
2. Otro repartidor no puede actualizar esa ubicación (`403`).
3. Un comercio ajeno no puede leerla (`403` o `404` sin revelar existencia).
4. Una entrega completada o cancelada rechaza nuevas posiciones (`409`).
5. Redis conserva la última posición con TTL y rechaza muestras fuera de orden.
6. El simulador reproduce el recorrido usando la API real; los mapas lo etiquetan como simulado.
7. La vista del destinatario funciona solo con token válido y expone datos mínimos.
8. Si falta permiso GPS, Redis o posición, la aplicación sigue mostrando el estado del pedido.
9. Temas claro/oscuro y diseño móvil funcionan correctamente.
10. Las pruebas locales no dependen de servicios AWS reales.

## 12. Plan de implementación para Codex

- **GEO-00 — Verificación:** revisar specs existentes y compatibilidad de MiniStack, documentar discrepancias.
- **GEO-01 — Contratos:** añadir DTOs, validaciones, puertos y OpenAPI, sin romper endpoints previos.
- **GEO-02 — Backend:** implementar adaptador Redis y endpoints con permisos y pruebas.
- **GEO-03 — Simulador:** generar recorrido de prueba a través del endpoint real.
- **GEO-04 — Frontend:** implementar mapa y controles siguiendo la skill `frontend-design`, con temas claro/oscuro.
- **GEO-05 — Validación:** pruebas integradas, seguridad, errores, documentación y demostración.

**Instrucción obligatoria para Codex:** antes de implementar la interfaz, localizar, leer y aplicar la skill `frontend-design` disponible en su entorno. No afirmar que la utilizó si no está instalada; reportarlo.

**No iniciar GEO-02 o fases posteriores hasta contar con un flujo funcional de creación, aceptación y actualización de entregas.**
