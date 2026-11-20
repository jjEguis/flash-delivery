# Seguimiento vial durante entregas — SPEC-08 v2

Implementación de [SPEC-08 v2](../specs/SPEC-08_LIVE_DELIVERY_TRACKING_v2.md), que sustituye el alcance geográfico anterior. Las entregas funcionan sin GPS; la posición se comparte únicamente en ASSIGNED/PICKED_UP. [Validación](../validation.md), [diseño](DISENO-V2.md), [compatibilidad](GEO-00-V2.md).

## Arranque local

Desde la raíz, con Docker, Node 22.12+ y la configuración de `.env.example`:

```bash
# Primera preparación: descarga Colombia (~318 MB), recorta Santa Marta y prepara MLD.
docker compose --profile geo-prepare run --rm osm-download
docker compose --profile geo-prepare run --rm osrm-prepare
# Los siguientes arranques reutilizan los archivos procesados.
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m scripts.demo
npm --prefix frontend ci
npm --prefix frontend run build:local
```

Abrir http://127.0.0.1:8080. `npm run dev:preview` desde `frontend/` sirve la aplicación en :5173 con proxy `/api/` hacia :8080. La sesión pertenece a cada origen; usar el mismo origen para todas las vistas de una sesión.

OSRM 5.27.1 funciona solo en la red Docker `local`; no publica puertos al host. El runtime Lambda local consulta `http://osrm:5000`, nunca localhost ni el servidor público de demo. La preparación usa el perfil `car.lua`, extract → partition → customize; `processed.ok` solo se crea al terminar. El healthcheck realiza una consulta de ruta válida, con timeout Docker configurable. Los archivos permanecen en `osrm-data` y no se regeneran al arrancar. Para cambiar fuente, cobertura o versión del motor, preparar un volumen nuevo explícitamente; no borrar los volúmenes de MiniStack/Redis.

## Procedencia OSM

Fuente: [Colombia de Geofabrik](https://download.geofabrik.de/south-america/colombia.html), OpenStreetMap, licencia [ODbL 1.0](https://www.openstreetmap.org/copyright). Extracción con vías completas en bbox oeste/sur/este/norte `-74.28,11.12,-74.05,11.36`. No se infieren posiciones a partir de direcciones.

Preparación observada: descarga **2026-11-17**, datos hasta **2026-11-16T21:22:36Z**. SHA-256 del PBF original: `5aacc48a344f70ea5b208ead065e79bfbee46698c5129a0ed3f153a5a533c6e3`. `/data/source.json` conserva URL, fecha, licencia, bbox, hash y metadata de Osmium. `OSM_PBF_URL` admite un PBF archivado para repetir exactamente una versión; la URL `latest` cambia con el tiempo. Los PBF y derivados no entran en Git.

## Demostración en sesiones independientes

Para probar también registro y aprobación administrativa, seguir la [demo guiada completa](../demo/README.md) con usuarios nuevos.

1. Comercio `tienda_demo`: crear un pedido, escribir direcciones y abrir «Seleccionar puntos en el mapa». Elegir recogida y entrega o pulsar «Usar puntos de demo de Santa Marta». Publicar y conservar el enlace público.
2. En otro perfil de navegador, repartidor `rep_demo1`: activar disponibilidad, aceptar el pedido y abrir «Compartir ubicación».
3. Elegir «Simulación de desarrollo», seleccionar un inicio en el mapa o «Usar inicio de demo en Santa Marta», marcar el consentimiento e iniciar. El primer punto se envía por API y el backend calcula la ruta vial a recogida.
4. Ajustar velocidad (1–25 m/s), pausar, reanudar o reiniciar. El avance usa distancia acumulada y reloj monotónico; las muestras usan UTC y secuencia. No se superponen envíos. «Simular desvío» desplaza tres muestras aproximadamente 110 m al norte; el recálculo espera el cooldown de 30 s y puede fallar si no hay vía cercana. Eso conserva la ruta anterior desactualizada y oculta la ETA.
5. Comercio abre el mapa desde el detalle; destinatario entra desde el enlace público. Ambos ven muestras por API, ruta recorrida/pendiente, estado, última actualización y ETA aproximada. Todos los mapas etiquetan SIMULATED.
6. «Marcar recogido» detiene la simulación anterior y prepara la ruta hacia destino. Pulsar Iniciar simulación de nuevo usa la última posición y conserva velocidad; si caducó, elegir un nuevo inicio. Al completar cada recorrido el mensaje indica confirmar recogida o entrega. El final de la simulación no entrega el pedido. «Marcar entregado» usa el comando autorizado existente y termina el seguimiento. También se oculta al cancelar/fallar, aunque falle la limpieza Redis.
7. Para GPS, elegir «GPS del navegador», consentir y activar. Denegar permiso permite continuar por estados. Detener, salir del mapa o cerrar sesión libera watcher y temporizadores. GPS exige HTTPS o localhost; no se promete continuidad con la pestaña cerrada.

El simulador se habilita con `build:local`/Vite DEV y, además, `ENVIRONMENT=local` + `TRACKING_SIMULATION_ENABLED=true` en backend. CDK utiliza false por defecto; Compose lo activa explícitamente para la demo local. `npm run build` omite los controles de demo. Reiniciar una pestaña no reanuda automáticamente ni salta al destino.

## Contratos y migración

Se mantienen todos los endpoints `/api/v1` y sus permisos/idempotencia. Se añaden:

| Contrato | Comportamiento |
| --- | --- |
| `POST /orders` | `pickupLocation` y `dropoffLocation` opcionales, ambos juntos, con latitude/longitude finitas y dentro de cobertura. Pedidos antiguos y creación sin puntos siguen funcionando por estados/GPS sin ruta. |
| `POST /orders/{orderId}/location` | Contrato anterior más sequence entero seguro no negativo, speedMps 0–100 y headingDegrees [0,360), opcionales. SIMULATED requiere configuración de desarrollo en backend. |
| `GET /orders/{orderId}/route` | Comercio propietario o repartidor asignado; geometría GeoJSON lon/lat, fase, versión, cálculo, progreso, distancia pendiente y ETA nullable. |
| `GET /tracking/{token}/route` | Token vigente/revocable, proyección sin identidad, direcciones, instrucciones ni anotaciones internas de segmentos. |

No hay nuevas tablas ni índices. ORDER/META guarda **solo los dos puntos estáticos del pedido**, como enteros E6 para conservar el esquema JSON/DynamoDB sin floats. Se proyectan a grados en el DTO de detalle y no en listados de ofertas. Esto amplía la decisión anterior «sin coordenadas en DynamoDB»: las muestras de movimiento siguen exclusivamente en Redis, sin histórico. Ambos puntos forman parte de la huella de idempotencia de creación. Los pedidos existentes no requieren backfill.

`tracking:order:{id}:latest` conserva posición por 120 s. La comparación Lua de timestamp/secuencia precede al límite por repartidor/pedido; duplicados y muestras antiguas no renuevan TTL. FRESH dura 15 s, después STALE; tras 120 s desde la muestra resulta UNAVAILABLE aunque aún quede TTL de recepción. Se conserva la credencial aleatoria, vencimiento y revocación de v1.

Snapshots en `tracking:order:{id}:route:{fase}`, TTL 300 s, con progreso y duraciones/distancias de segmentos OSRM. Se invalidan por fase, edad o desvío. Una muestra solo avanza el progreso una vez, mediante comparación atómica de época y versión. Tres muestras válidas a más de 50 m activan recálculo (umbral ajustado por precisión, hasta 200 m); cooldown 30 s. El lock con expiración y nonce verifica propiedad, versión y última muestra antes de publicar; un propietario vencido no sobrescribe al sucesor. Un contador entero por pedido, sin coordenadas, mide llamadas y vence con el TTL de ruta.

Cada lectura/escritura valida el estado oficial con lectura fuerte. Tras OSRM se revalida fase/asignación, y antes de devolver ruta se revalida estado y token. Una carrera con cierre puede dejar un snapshot residual, pero las lecturas terminales lo ocultan. Redis/OSRM no modifican estados automáticamente ni forman una transacción distribuida con DynamoDB.

## Interfaz y configuración

MapLibre GL JS **6.19.0**, worker empaquetado localmente con Vite. Se retiró Leaflet. Claro/oscuro, Manrope y tokens existentes; marcador con heading, pins R/E, centrado automático desactivable, zoom y ruta completa. La animación interpola sobre geometría durante un segundo, termina en la muestra y respeta `prefers-reduced-motion`; no extrapola ni representa una medición GPS adicional. Polling cada 5 s en vista visible, sin solapamiento, backoff de errores y parada en estados terminales. Coordenadas/frescura textuales y timeline permanecen disponibles cuando falla el mapa.

OSRM no proporciona tiles, geocodificación ni tráfico. Tiles OSM separados, atribuidos y sujetos a su [política de uso](https://operations.osmfoundation.org/policies/tiles/); no hay descargas masivas. Configurar `VITE_MAP_STYLE_URL` para un estilo completo o `VITE_MAP_TILE_URL` + `VITE_MAP_ATTRIBUTION` para raster. El estilo local ajusta brillo y ruta para tema oscuro. El servidor estático usa `Referrer-Policy: strict-origin` para identificar el origen ante el proveedor sin enviar rutas ni query. La API conserva `no-referrer`. Los tokens van en el fragmento, nunca en solicitudes al proveedor cartográfico.

Configuración completa en `.env.example` y `frontend/.env.example`: `OSRM_URL`, `OSRM_TIMEOUT_SECONDS=3`, `ROUTING_BBOX`, `ROUTE_TTL_SECONDS=300`, `ROUTE_DEVIATION_METERS=50`, `ROUTE_RECALCULATE_SECONDS=30`, `LOCATION_TTL_SECONDS=120`, `LOCATION_FRESH_SECONDS=15`, `LOCATION_MIN_INTERVAL_MS=3000`. `VITE_GEO_INTERVAL_MS` admite 3000–5000 ms (4000 inicial). Los env de backend se propagan desde Compose por CDK al provisionar. OSRM usa WARNING para evitar access logs con coordenadas; los logs de negocio registran plantillas de ruta y medidas sin tokens/coordenadas.

## Validación reproducible

```bash
docker compose exec -T cdk-dev python -m pytest tests/ -q
docker compose exec -T cdk-dev python -m pytest tests/integration/ -m integration -q
cd frontend
npm run build
npm run lint
npm test
npm run test:design
npx playwright install chromium
npm run test:e2e
npm run test:design:e2e
npm run test:geo:e2e
npm run test:geo:production
npm run test:unified:e2e
npm run build:local
npm run test:geo:real
```

El smoke real usa Python de `../.venv/bin/python` con boto3/python-dotenv, configurable con `GEO_PYTHON`. `GEO_EVIDENCE_DIR` guarda capturas sin trazas/tokens. Fixtures temporales privados se limpian por claves exactas, incluidas rutas. En esta sesión se instaló Chromium bajo `/tmp/flashdelivery-playwright`; se usó `PLAYWRIGHT_BROWSERS_PATH` apuntando allí, sin modificar configuración del host.

La integración genera `app/.local/live-routing-metrics.json`: latencias HTTP p50/p95 y llamadas reales a OSRM, con 17 operaciones contractuales distintas. Mide una muestra pequeña local, sin equivalencia con AWS ni SLA. Se prueban proveedor falso, NoRoute, timeout, NoSegment/puerto inaccesible real, progreso, fase, TTL, permisos, revocación, lock vencido, desvío/cooldown y concurrencia real. [Resultados y capturas](../validation.md).

## Límites observados

Perfil automóvil como aproximación; ETA por segmentos sin tráfico real ni modelo específico de motocicleta. La geometría puede cambiar al recalcular; no hay geocodificación, historial de ubicaciones ni navegación completa. Si falla OSRM se oculta ETA y se conserva una ruta anterior marcada obsoleta cuando existe; sin ruta calculada se mantiene seguimiento por estados.

NoRoute se valida con respuesta controlada; el extracto real devolvió NoSegment para un punto sin vía cercana y se probó rechazo de conexión. El GPS de teléfono y lector de pantalla humano siguen sin validarse. El mapa depende de WebGL y de tiles externos; dispone de alternativa textual. MiniStack emula las operaciones probadas, no todos los servicios AWS. Su CloudWatch local conserva START/END/REPORT, pero no los logs de aplicación observados; la medición de llamadas usa el contador Redis efímero. La compilación advierte del tamaño del bundle de MapLibre. `npm audit` señala 11 alertas altas del toolchain preexistente; la dependencia MapLibre añadida quedó sin la alerta crítica detectada en 5.15.0. No se aplicó una migración del toolchain fuera de esta SPEC.
