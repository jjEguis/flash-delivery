# SPEC-08 — Ubicación durante entregas activas

GEO-00 a GEO-05 implementadas. [Verificación previa](GEO-00.md), [SPEC](../specs/SPEC-08_GPS_TRACKING.md), [contrato](../api/openapi.json) y [validación](../validation.md).

## Cómo probarlo

Con Docker y Node 22.12+:

```bash
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
cd frontend
npm ci
npm run build:local
```

Abrir http://127.0.0.1:8080. La aplicación funcional completa se compila con Vite y utiliza el diseño aprobado. Los mapas se abren dentro de la misma navegación en `#/ubicacion/<id>` y `#/mapa/<token>`. Los enlaces antiguos a `/design-dist/geo.html` redirigen a esas rutas. El prototipo FE-01 permanece como referencia explícita en `preview.html`; :8080 usa exclusivamente los servicios reales.

1. Comercio `tienda_demo`: crear un pedido nuevo y guardar el enlace de seguimiento. Si no existen los perfiles de demostración, ejecutar `docker compose exec -T cdk-dev python -m scripts.demo` antes de probar.
2. En otro navegador o perfil, repartidor `rep_demo1`: activar disponibilidad y aceptar ese pedido. En «Pedido activo», abrir «Compartir ubicación».
3. En el panel de seguimiento, seleccionar simulación, marcar el consentimiento e iniciar. Se envían ocho puntos de prueba cada cuatro segundos a la API real. Pausar, reanudar y reiniciar conservan el contrato; detener borra la posición. Finalizar el recorrido no marca el pedido como entregado.
4. En Comercio, abrir el detalle y «Ver ubicación de la entrega». El destinatario abre el enlace compartido y «Ver ubicación compartida». Ambas vistas consultan la posición cada cinco segundos y señalan «Modo simulación · Recorrido ficticio».
5. Marcar recogido y entregado en la aplicación del repartidor. Los mapas dejan de mostrar coordenadas y el servidor rechaza nuevas muestras. También se limpia al cancelar o marcar fallido.
6. Para GPS, elegir «GPS del navegador», marcar el consentimiento y activar. El navegador solicita permiso; denegarlo permite continuar por estados. Requiere HTTPS o localhost. Detener, cerrar la página o cambiar la sesión detiene el watcher; cerrar sesión en otra pestaña elimina la muestra mediante una petición de limpieza best effort.

La vista geográfica recibe la sesión activa de la aplicación y comparte su selector de tema. Navegar al mapa y volver mantiene la sesión, incluso cuando el almacenamiento está bloqueado. Al navegar fuera del mapa se desmonta el watcher y se detienen sus temporizadores. Para probar el flujo real usar :8080; la sesión no se comparte entre orígenes. El cierre forzado del navegador puede impedir la petición de limpieza; el TTL y el estado oficial limitan el acceso.

## Arquitectura y datos

```text
GPS con consentimiento / recorrido ficticio
         │ HTTP autenticado
         ▼
Tracking Lambda → OrderReader → ORDER#id / META (lectura fuerte)
         │ permisos, estado activo, validación
         ▼
LocationStore → Redis (Lua: orden temporal + límites + SET con TTL)
         ▲
comercio propietario / repartidor asignado / destinatario con token
```

No se escriben coordenadas en DynamoDB ni se crea tabla o GSI. El nuevo ítem `ORDER#id / TRACKING`, sin índices, guarda nonce aleatorio de 256 bits, vencimiento y revocación. Se crea en la transacción inicial junto al pedido. HMAC con clave del servidor y nonce permite recuperar el mismo token en reintentos; META conserva solo el hash verificable. El nonce no es el secreto público ni permite deducirlo sin la clave. Este ítem no expira físicamente, para evitar que desaparezca una revocación y se interprete el token como histórico. No es un histórico de ubicaciones.

Los tokens nuevos vencen a las 24 horas y el comercio puede revocarlos desde el mapa. El endpoint de revocación es idempotente. No se incluye renovación en esta fase. Los enlaces anteriores a SPEC-08 siguen mostrando estados pero no autorizan ubicación; crear un pedido nuevo para probar el mapa público. El secreto local por defecto sigue siendo de desarrollo, igual que la autenticación existente.

## Contrato y configuración

Todas las rutas tienen prefijo `/api/v1`.

| Ruta | Permiso y resultado |
| --- | --- |
| `POST /orders/{orderId}/location` | Solo asignado en ASSIGNED/PICKED_UP; 202 con `accepted`; false si la muestra es anterior o duplicada |
| `GET /orders/{orderId}/location` | Comercio propietario o repartidor asignado; otros comercios 404, roles ajenos 403 |
| `DELETE /orders/{orderId}/location` | Asignado; 204; sustituye coordenadas por tombstone temporal que rechaza muestras atrasadas |
| `GET /tracking/{token}/location` | Token nuevo válido, vigente y no revocado; respuesta mínima sin IDs de participantes ni direcciones |
| `DELETE /orders/{orderId}/tracking-token` | Comercio propietario; 204; revoca el enlace de estados y ubicación |

Posiciones finitas, latitud ±90, longitud ±180, precisión opcional no negativa, fuente SIMULATED/BROWSER_GPS, fecha UTC con sufijo Z. Edad máxima 120 s y futuro máximo 15 s; errores semánticos 422. El JSON HTTP mal formado conserva el error 400 existente. Redis limita por pedido y repartidor; el router mantiene además su límite general. Ningún campo del cuerpo define la identidad.

| Variable Lambda | Valor inicial |
| --- | --- |
| `LOCATION_TTL_SECONDS` | 120 |
| `LOCATION_FRESH_SECONDS` | 30 |
| `LOCATION_MIN_INTERVAL_MS` | 3000 |
| `TRACKING_TOKEN_TTL_SECONDS` | 86400 |

El registro CDK propaga estas variables al provisionar. `tracking:order:{id}:latest` guarda la última muestra y el ID interno del repartidor; la respuesta filtra ese ID. Muestras antiguas no renuevan TTL. Las claves de límite duran el intervalo configurado. FRESH dura 30 s; STALE indica última ubicación conocida; al vencer desaparece y resulta UNAVAILABLE.

Dispatch limpia la posición después de confirmar DELIVERED/CANCELLED/FAILED. Si Redis falla, no revierte la transacción: las lecturas verifican el estado fuerte de META, no devuelven coordenadas terminales y el TTL actúa como respaldo. Publicar revalida el estado después de escribir. Redis y DynamoDB no forman una transacción distribuida: una lectura concurrente puede representar el estado válido en el instante de comprobación; no se promete revocación retroactiva de respuestas ya enviadas.

## Mapas, compilación y límites

Leaflet 1.9.4 se empaqueta localmente. Los tiles proceden de OpenStreetMap, con atribución visible, HTTPS, caché normal del navegador y Referer de origen; los tokens permanecen en el fragmento de navegación y se omiten de los logs del proxy. El fondo cartográfico es un servicio externo, sin SLA; si falla, permanecen marcador, coordenadas textuales y estado. No hay prefetch, descargas masivas, ETA ni ruta por calles. El estilo oscuro adapta la interfaz y controles, conserva los tiles originales y no altera la atribución. Se puede sustituir el proveedor con `VITE_MAP_TILE_URL`; al cambiarlo también debe adaptarse su atribución y política.

`npm run build` excluye los controles de simulación. `npm run build:local` los habilita explícitamente y deja la compilación local disponible en :8080. El servidor `npm run dev:preview` también los habilita en desarrollo; `/geo.html` usa proxy hacia :8080. El intervalo del simulador admite `VITE_GEO_INTERVAL_MS` (mínimo 3000; inicial 4000). Sus puntos son ficticios y no describen calles reales.

No se garantiza seguimiento en segundo plano ni continuidad con la pestaña cerrada. El GPS físico no se validó con un teléfono: se comprobó el contrato con callbacks controlados en Chromium y el recorrido completo con la API real. La accesibilidad se verificó con axe y controles de teclado; falta revisión humana con lector de pantalla.

## Pruebas reproducibles

```bash
docker compose exec -T cdk-dev python -m pytest tests/ -q
docker compose exec -T cdk-dev python -m pytest tests/integration/test_geo_http_integration.py tests/integration/test_api_flow.py -m integration -q
cd frontend
npm run build
npm run lint
npm run test:design
npm test
npx playwright install chromium
npm run test:design:e2e
npm run test:e2e
npm run test:geo:e2e
npm run test:geo:production
npm run test:unified:e2e
npm run build:local
npm run test:geo:real
```

El último smoke requiere la API real, :8080, y Python local con boto3/python-dotenv (por defecto `../.venv/bin/python`, configurable con `GEO_PYTHON`). Crea actores/pedido aislados y limpia por claves exactas, incluidas credenciales de tracking y límites Redis. Sus credenciales temporales van a un archivo privado en `/tmp`, no a logs o capturas de trazas. Las pruebas unitarias usan moto/fakeredis con Lua mediante lupa. CI ejecuta unitarios, regresiones, mapas y la exclusión del simulador; las integraciones reales se seleccionan expresamente.

Capturas del smoke con API real: [comercio claro](../evidencias/spec08/comercio-claro-1440.png), [destinatario oscuro móvil](../evidencias/spec08/destinatario-oscuro-390.png).

La unificación visual posterior a la primera entrega de SPEC-08 está documentada en [UNIFICACION](../frontend/UNIFICACION.md). No cambia los contratos HTTP ni la persistencia.
