# SPEC-08 v2.0 — Live Delivery Tracking

**Proyecto:** FlashDelivery
**Estado:** Implementada (GEO-00 a GEO-05), validada localmente; pendiente revisión del PR
**Prioridad:** Después del flujo de entregas
**Entorno actual:** MiniStack + Redis + OSRM en Docker
**Arquitectura:** Monolito modular serverless (Python, Lambda, API Gateway, DynamoDB Single Table Design)

Implementación, migración y límites: [guía GEO](../geo/README.md). Compatibilidad previa: [GEO-00 v2](../geo/GEO-00-V2.md). Evidencias: [validación](../validation.md) y [diseño aplicado](../geo/DISENO-V2.md).

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
- Optimización de múltiples paradas, ETA con tráfico real, navegación giro a giro completa, seguimiento en segundo plano con navegador cerrado, geocercas, histórico exhaustivo de coordenadas, facturación por distancia y WebSockets.

## 3. Componentes y límites de módulo

- **Frontend / Courier:** obtiene coordenadas con `navigator.geolocation.watchPosition` cuando el usuario lo habilita; detiene el seguimiento al finalizar/cancelar o cerrar sesión. En simulación genera puntos de una ruta de prueba. No accede directamente a Redis ni DynamoDB.
- **Tracking:** propietario de `POST location` y `GET latest location`; valida permisos, estados, frescura y coordenadas; usa puertos `LocationStore` y `OrderReader`.
- **Orders:** fuente de verdad del estado de la entrega y relación con comercio y repartidor.
- **Dispatch:** asignación transaccional; no modifica posiciones.
- **Redis:** última posición efímera por pedido con TTL.
- **DynamoDB:** estado oficial de la entrega y eventos de cambio de estado. No escribir cada muestra GPS en la tabla principal en esta fase.
- **Map UI:** MapLibre GL JS con estilos claro/oscuro y proveedor de tiles compatible con su licencia; atribución OpenStreetMap y del proveedor.

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

- Obtener una ruta vial real de OSRM en Santa Marta y recorrer su geometría según distancia acumulada y velocidad configurable; no mover el marcador en línea recta entre origen y destino.
- Controles visibles en desarrollo: iniciar, pausar, reanudar, reiniciar y detener.
- Emitir una posición cada 3–5 segundos (configurable), a través del mismo contrato HTTP que el GPS real.
- No permitir iniciar si el usuario no es el repartidor asignado a una entrega activa.
- Señalizar claramente `Modo simulación` en todos los mapas y nunca representar posiciones simuladas como reales.
- Mantener los controles de simulación fuera de la interfaz de producción.

## 8. Interfaz y UX

- Seguir `SPEC-07_FRONTEND_DESIGN_v2.1.md`, con tema claro/oscuro y responsive.
- **Comercio:** tarjeta de seguimiento con mapa, estado, hora de última posición y aviso de datos obsoletos.
- **Repartidor:** interruptor explícito para compartir ubicación, estado del permiso, indicador de envío y botón de detener; simulador solo en desarrollo.
- **Destinatario:** mapa con marcador animado, ruta restante, ETA estimada y estado; ocultar ETA si no hay cálculo válido.
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
- **GEO-03 — Simulador:** generar recorrido vial mediante OSRM a través del endpoint real.
- **GEO-04 — Frontend:** implementar mapa MapLibre, animación, ruta restante, ETA y controles siguiendo la skill `frontend-design`, con temas claro/oscuro.
- **GEO-05 — Validación:** pruebas integradas, seguridad, errores, documentación y demostración.

**Instrucción obligatoria para Codex:** antes de implementar la interfaz, localizar, leer y aplicar la skill `frontend-design` disponible en su entorno. No afirmar que la utilizó si no está instalada; reportarlo.

**No iniciar GEO-02 o fases posteriores hasta contar con un flujo funcional de creación, aceptación y actualización de entregas.**


## 13. Motor geográfico y experiencia profesional (normativo)

Esta sección amplía los requisitos anteriores; ante discrepancias prevalece esta versión. El docente confirmó que OSRM auxiliar es admisible mientras la base exigida conserve su arquitectura serverless. No se migrará a AWS real.

### GEO-01 — Infraestructura geográfica
- OSRM autohospedado en Docker Compose, con imagen versionada y extracto OSM de Santa Marta y área circundante suficiente para conectar recorridos. Documentar origen, fecha y licencia del PBF. Preparar datos con osrm-extract (perfil driving), osrm-partition y osrm-customize; ejecutar osrm-routed --algorithm mld. Persistir archivos procesados, no regenerarlos en cada arranque. Healthcheck mediante consulta de ruta válida y timeout configurable.
- OSRM no sirve tiles, no geocodifica direcciones y no suministra tráfico en vivo. MapLibre necesita un estilo y fuente de tiles independientes, configurables y con atribución. Para la demo seleccionar recogida y destino mediante mapa; geocodificación por adaptador opcional. No depender de un endpoint público OSRM de demostración.
- Lambda consume OSRM por red interna mediante RoutingProvider; comprobar conectividad desde el runtime MiniStack, no asumir localhost. No exponer OSRM públicamente. Redis y DynamoDB conservan sus responsabilidades. No crear un backend persistente adicional de negocio.
- Usar Route API (`/route/v1/driving/{lon,lat};{lon,lat}?overview=full&geometries=geojson&steps=true`) y validar respuestas. GeoJSON usa longitud, latitud. DTO interno: geometry, distanceMeters, durationSeconds, steps opcionales, calculatedAt, routeVersion, phase. Proteger llamadas con timeout y manejar NoRoute/sin conectividad.
- Perfil automóvil como aproximación inicial, no afirmar rutas específicas de motocicleta o tráfico en tiempo real.

### Contratos adicionales
- `GET /orders/{orderId}/route`: comercio propietario o repartidor asignado; devuelve geometría, distancia restante, ETA, fase y versión. `GET /tracking/{token}/route`: proyección pública mínima, con autorización equivalente al endpoint de ubicación. Alinear rutas y modelos con OpenAPI existente.
- Añadir coordenadas de recogida y entrega al contrato existente de creación de pedido de forma compatible; no inferir coordenadas de una dirección sin resolver. Validar rangos y cobertura. Conservarlas en ORDER/META.
- Ampliar DTO de posición con sequence, speedMps y headingDegrees opcionales; validar valores finitos, secuencia y timestamps; repetir una muestra no debe renovar su TTL. Cachear ruta por pedido/fase/versión, invalidar al cambiar fase o detectar desvío. Caducidad configurable. Usar Redis para snapshots de ruta y progreso, no como autoridad de estados.

### GEO-02 — Progreso, ETA y desvíos
- ASSIGNED: ruta desde ubicación del repartidor a recogida. PICKED_UP: ruta desde ubicación actual al destinatario. Antes de la primera posición mostrar puntos sin inventar origen. Estados terminales desactivan seguimiento y rutas públicas activas.
- Proyectar posición a la geometría y calcular distancia restante acumulada. Evitar saltos en cruces usando progreso previo; si posición está lejos de la ruta, no fingir que sigue sobre ella. ETA aproximada a partir de duración de segmentos restantes de OSRM (solicitar annotations=duration,distance cuando proceda), actualizar según progreso; mostrar hora de cálculo, sin tráfico real. No consultar OSRM en cada muestra.
- Detectar desvío con distancia a ruta superior a 50 m durante tres muestras válidas consecutivas (ajustable según precisión); recalcular con cooldown inicial de 30 s. Evitar recálculos duplicados mediante lock Redis con expiración, comparar versión antes de publicar. Si falla OSRM conservar ruta anterior marcada desactualizada o mostrar seguimiento por estados.
- Consultar estado oficial en cada lectura/escritura de seguimiento, preferir lectura consistente del pedido; ante carrera con cierre, las lecturas deben ocultar datos de pedidos terminales incluso si la limpieza Redis falla. No alterar estados automáticamente por GPS.

### GEO-03 — Simulador avanzado
- Movimiento por distancia acumulada sobre geometría, velocidad configurable, pausa/reanudación, cambio de velocidad y escenario de desvío reproducible. Usar reloj monotónico para avance y UTC para muestras. Enviar por API real cada 3–5 s, sin llamadas superpuestas; detener ante 401/403/409 y respetar 429. No saltar a destino por reinicio de pestaña. Marcar toda sesión como SIMULATED; habilitar solo mediante configuración de desarrollo validada en backend. La finalización de la entrega sigue el flujo de estados autorizado.

### GEO-04 — UX tipo aplicaciones logísticas
- MapLibre con ruta recorrida/pendiente diferenciada, marcador orientado por heading, pins de recogida y entrega, centrado automático desactivable, zoom y vista de ruta completa. Animar entre muestras con requestAnimationFrame; no extrapolar indefinidamente ni presentar interpolación como GPS medido. Respetar prefers-reduced-motion. Limpiar timers, watchers y mapas al desmontar.
- Polling HTTP cada 3–5 s mientras entrega activa y vista visible; detener al finalizar, backoff ante fallos, evitar respuestas fuera de orden. Indicadores de frescura: inicial FRESH hasta 15 s, luego STALE hasta expiración 120 s, UNAVAILABLE después. Mostrar última actualización, señal y ETA aproximada. No introducir WebSockets en esta fase.
- Comercio: detalle con mapa, estado, ETA, distancia y timeline. Repartidor: vista móvil con ruta a recogida/entrega y siguiente instrucción si disponible, botones de estados existentes, compartir ubicación y demo. Destinatario: mapa, ETA, estado y timeline mínimo; sin identidad sensible. Administrador: diagnóstico secundario sin acceso indiscriminado a GPS. Aplicar skill frontend-design y SPEC-07 v2.1, ambos temas y accesibilidad.

### GEO-05 — Aceptación adicional
- Validar OSRM local con una ruta real entre dos puntos de Santa Marta; comprobar geometría, distancia y ETA válidas; probar NoRoute y caída de servicio. Verificar cambios de fase y recálculo ante desvío, cooldown y concurrencia.
- Demostrar dos sesiones independientes (repartidor y comercio/destinatario) sincronizadas por API real; comprobar que marcador sigue calles y ETA cambia con progreso; probar muestras desordenadas, pausa, expiración, permisos, cierre y revocación de token.
- Ejecutar pruebas unitarias con proveedor falso, integración con OSRM/Redis/MiniStack reales locales y E2E en ambos temas. Medir latencia p50/p95 y frecuencia de llamadas a OSRM; reportar valores observados, no inventarlos. Verificar al menos diez operaciones HTTP funcionales del proyecto según rúbrica.
- Entregar Compose actualizado, scripts de preparación OSM, OpenAPI, configuración de ejemplo sin secretos, instrucciones de demo y resultados de pruebas. No declarar completo si un servicio no funciona. No modificar contratos previos sin documentar migración; mantener flujo de entregas funcional sin GPS.
