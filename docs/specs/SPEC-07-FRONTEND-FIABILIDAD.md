# SPEC-07 — Reintentos, paginación y pruebas del frontend

**Estado:** implementada. **Fecha:** 2026-11-15.

## Problema y alcance

La SPA descartaba una Idempotency-Key después de una respuesta 2xx cuyo cuerpo no se pudo leer. Reintentar podía crear otra intención aunque el servidor hubiera confirmado la primera. Además, el repartidor solo veía los primeros 20 pedidos abiertos y 10 registros del historial, y CI no ejecutaba pruebas del frontend.

Esta SPEC incorpora cliente HTTP, estado de listas paginadas y pruebas automatizadas. Mantiene la interfaz sin dependencias de ejecución ni paso de compilación. No modifica contratos de API, transacciones de negocio ni diseño visual.

## Reintentos

- `frontend/api.js` conserva la clave ante errores de red, JSON ilegible, respuesta exitosa incompleta, 401/403, 408, 429, 5xx y `CONCURRENT_UPDATE`. Reautenticar o recuperar permisos no debe descartar una intención anterior de resultado incierto; el mismo actor puede retomarla con su nueva sesión.
- Una respuesta JSON válida y conforme al resultado esperado confirma la intención y elimina su clave pendiente. HTTP 204 confirma sin cuerpo. Los restantes errores 4xx definitivos liberan la intención; una corrección posterior tendrá otra clave.
- La creación de pedidos verifica `orderId` y `trackingToken` antes de confirmar, limpiar el formulario o mostrar el enlace.
- Una huella SHA-256 de rol, actor, método, ruta, cuerpo canónico e intención identifica la acción. El orden de propiedades JSON no altera la huella; otro actor, rol, cuerpo u operación no hereda la clave.
- `fd.pendingRequests.v1` guarda únicamente huellas y claves, sin direcciones, cuerpos ni tokens de sesión. Una recarga recupera la clave al reenviar la misma acción con el mismo cuerpo. El formulario no se guarda: después de recargar hay que volver a introducir los mismos datos.
- Si localStorage está bloqueado, existe respaldo en memoria durante la página actual, pero no se garantiza recuperación después de recargar. No se ofrece exclusión mutua entre pestañas ni sincronización entre dispositivos.
- Las intenciones pendientes no expiran automáticamente: eliminarlas antes de resolver una respuesta incierta podría permitir duplicados. El usuario puede borrarlas al limpiar el almacenamiento del navegador, perdiendo esa recuperación.
- Una respuesta 401 tardía no cierra la sesión de otro usuario. Un login fallido sin sesión no dispara logout.

## Paginación del repartidor

`frontend/pagination.js` mantiene elementos, cursor y número de páginas cargadas. «Cargar más pedidos» usa el cursor de `/orders/available`; «Cargar más historial» usa el de `/couriers/me/orders`. Los cursores se envían como valores opacos mediante URLSearchParams.

Los elementos se deduplican por orderId, actualizando sus datos si aparecen en más de una página. Una carga fallida conserva elementos y cursor para reintentar. Las solicitudes de una misma lista se serializan para no cargar dos veces la misma página por doble clic.

«Actualizar pedidos» y el refresco periódico vuelven a consultar las páginas ya cargadas. Solo publican el nuevo estado si se completó toda esa lectura: un error intermedio no borra las páginas visibles. La lista sigue siendo eventualmente consistente, sin snapshot entre páginas. Los botones «Aceptar» permanecen deshabilitados cuando hay pedido activo o el repartidor no está disponible.

## Pruebas y CI

| Nivel | Cobertura |
| --- | --- |
| Node `node:test` | Reintentos, cuerpos inválidos, 204/4xx/5xx, persistencia al recargar, separación por actor/rol/operación, almacenamiento bloqueado, 401 tardío; páginas, errores, refresco y doble clic |
| Playwright con API simulada | Login, pedido 21 e historial 11, refresco con varias páginas, aceptar desde una página posterior, error de segunda página y reintentos de creación tras JSON perdido/red/503 y recarga |
| Playwright contra API real | Health y zonas por proxy, login y formulario de alta de un usuario temporal; sin crear perfiles ni pedidos |

Los casos con API simulada se ejecutan en Chromium de escritorio y Chromium con viewport/touch de iPhone 13; no equivalen a pruebas de Safari/iOS. El servidor de tests usa el puerto 4173, sin reutilizar el servidor web de la demo y con upstream deliberadamente no operativo. No requiere Docker ni recursos de datos; las respuestas de la API se interceptan en cada contexto de navegador.

El job `frontend` de GitHub Actions instala con `npm ci`, ejecuta unitarios y Playwright, y conserva trazas de pruebas simuladas solo si fallan. La comprobación con API real es explícita y local, porque requiere el stack provisionado. Los tests Python anteriores se mantienen en su job separado.

Comandos desde `frontend/`:

```bash
npm ci
npm test
npx playwright install chromium
npm run test:e2e
# Con web y API local en marcha:
npm run test:smoke
```

En Linux puede ser necesario `npx playwright install --with-deps chromium`. El lock fija las dependencias de desarrollo; no se necesitan Node ni Playwright para servir la aplicación con Docker. Los resultados y trazas locales no se versionan ni entran en el contexto de construcción Docker.

## Criterios de aceptación

1. La respuesta 201 con JSON perdido no confirma un pedido vacío ni descarta la clave. Reintentar tras recargar confirma el mismo resultado en la API simulada con una sola escritura lógica.
2. Red y 503 conservan clave; éxitos confirmados y conflictos definitivos la liberan. El almacenamiento no contiene cuerpos ni credenciales.
3. Se puede ver y aceptar el pedido 21 y consultar el historial 11. El refresco no elimina las páginas adicionales.
4. Fallar al cargar una página no pierde filas ni cursor; el usuario puede reintentar.
5. Las pruebas pasan en escritorio y vista móvil, y CI valida el frontend además del backend.
6. El proxy y la API real responden después de provisionar la configuración actual. La evidencia diferencia simulaciones de comprobaciones reales.

Evidencia de ejecución en [validación](../validation.md). La garantía de no duplicar las mutaciones reales sigue perteneciendo a la idempotencia transaccional del backend; las pruebas de navegador con fallos simulados verifican que el cliente conserve y reenvíe su clave correctamente.
