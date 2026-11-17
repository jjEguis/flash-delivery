# Registro de validación

## Corrección de bloqueo de tiles — 2026-11-17

La captura del usuario mostró tiles de OSM con aviso 403. Se identificó `Referrer-Policy: no-referrer` en el servidor estático, incompatible con la identificación de origen exigida por el proveedor. El HTML y el worker ahora reciben `strict-origin`: los tiles envían únicamente el origen, sin ruta, query ni fragmento de seguimiento. Las respuestas de API y el cliente `geoApi` conservan `no-referrer`. Se mantiene el proveedor y su caché, sin rotar hosts ni añadir proxies.

Compilación normal/local correctas. Prueba de navegador contra `server.py`: **2 passed** (exclusión del simulador y regresión de encabezados). La nueva prueba intercepta tiles y API, comprueba Referer igual al origen y ausencia del token del fragmento. Se reinició `web` y se verificó la política en :8080 y en el worker. Referencia: [política oficial de OSM](https://operations.osmfoundation.org/policies/tiles/). Recargar la página es necesario para aplicar la nueva política al documento ya abierto.

## SPEC-08 v2 — rutas viales, progreso y ETA — 2026-11-17

Implementación de [Live Delivery Tracking v2](specs/SPEC-08_LIVE_DELIVERY_TRACKING_v2.md), sección 13 normativa. [Verificación previa](geo/GEO-00-V2.md), [guía, migración y limitaciones](geo/README.md), [diseño aplicado](geo/DISENO-V2.md). Se partió de `origin/develop` actualizado en `feature/spec-08-live-delivery-v2`.

| Comprobación | Resultado observado |
| --- | --- |
| Flujo HTTP antes de GEO-02 | **2 passed**, MiniStack/Redis reales: creación, aceptación, recogida y entrega |
| Compatibilidad desplegada | MiniStack **1.5.36**, Redis **7.4.2**, Python **3.12**, DynamoDB ACTIVE, **37 rutas API Gateway** (34 de módulos + salud) |
| Extracto/OSRM privado | **5.27.1 MLD**, Santa Marta; red interna desde Lambda y cdk-dev; consulta de referencia **31 puntos, 1642.6 m, 142.4 s**; healthcheck correcto |
| Backend moto/fakeredis | **147 passed, 19 deselected**, 18.78 s; sin red en unitarios |
| Integración local completa | **19 passed**, 32.76 s; OSRM/Redis/MiniStack reales, servicios, flujo previo y concurrencia conservados |
| Seguridad/progreso nuevos | DTO finito y cobertura, campos opcionales compatibles, secuencia/TTL, permisos, revocación, estado fuerte, cambio de fase, desvío/cooldown, lock vencido y cierre durante cálculo |
| Desvío/concurrencia reales | Tres muestras fuera de ruta, cooldown real acortado a 1 s en el test, seis consultas paralelas y **un solo recálculo**; contador por pedido con TTL |
| Compilación normal/local y lint | Correctos; MapLibre **6.19.0**, worker local emitido y Leaflet retirado; build normal sin controles de demo |
| Unitarios frontend | **22 + 7 passed**, HTTP/paginación y diseño |
| Navegador existente/diseño | **10 + 29 passed** |
| Mapa, permisos GPS y simulador vial | **16 passed**: ambos temas, 360/390/768/1440, axe, worker/canvas cargados, pausa/reinicio, GPS denegado, Redis/tiles caídos y polling sin solapamiento/parada terminal |
| Compilación de producción | **1 passed**, solo GPS con consentimiento, sin controles de simulación |
| Interfaz unificada | **58 passed**, incluido pedido con puntos de mapa; ambos temas, cinco anchos, teclado, contraste, sesión en memoria y regresiones previas |
| Tres sesiones con API real | **1 passed**, aproximadamente 1.4 min: repartidor, comercio y destinatario; recorrido por calles, progreso/ETA, pausa/reanudación, final del simulador y cierre autorizado de entrega |

Medición de una ejecución local, con 44 solicitudes cronometradas de 17 operaciones contractuales distintas: **p50 66.17 ms / p95 73.96 ms**. Se observaron **3 llamadas a OSRM**: cálculo inicial, recálculo por desvío y cambio a PICKED_UP; siete muestras antes del cambio de fase y diez lecturas repetidas no generaron otras llamadas. Las seis lecturas concurrentes adicionales verificaron el lock y se contabilizaron por separado de las 44 mediciones secuenciales. [Métricas agregadas originales](evidencias/spec08-v2/metrics.json). No es una prueba de carga ni una predicción de latencia en AWS.

Capturas del navegador con API real: [comercio claro 1440](evidencias/spec08-v2/comercio-claro-1440.png) y [destinatario oscuro 390](evidencias/spec08-v2/destinatario-oscuro-390.png). Se revisó visualmente ruta por calles, pins, posición, datos de ETA/distancia y disposición móvil. La skill `frontend-design` estaba instalada y se leyó antes de la interfaz. Tiles OSM independientes de OSRM, con atribución; no se usa un OSRM público de demo.

Compatibilidad: creación sin coordenadas y pedidos previos mantienen el flujo. Los puntos estáticos opcionales del pedido se almacenan como E6 en META; las muestras siguen solo en Redis, sin tablas ni GSIs nuevos. FRESH pasa de 30 a 15 s y SIMULATED se restringe también en backend. El administrador conserva diagnóstico por estados sin nuevos permisos GPS.

Límites: ETA aproximada con perfil automóvil, sin tráfico real; NoRoute se probó con respuesta controlada, NoSegment y conexión rechazada con OSRM local. GPS físico y lector de pantalla humano pendientes. WebGL y tiles externos tienen alternativas textuales. MiniStack conserva logs de runtime en CloudWatch local, pero no se observaron los mensajes de aplicación allí: las llamadas se midieron con contador Redis efímero sin coordenadas. La compilación avisa del bundle de MapLibre; `npm audit` conserva 11 alertas altas del toolchain anterior, sin la crítica de la primera versión de MapLibre considerada. No se actualizó ese toolchain fuera del alcance.

## Unificación de toda la interfaz funcional — 2026-11-16

Se aplica el diseño aprobado a acceso, registro/habilitación, comercio, repartidor, administración, seguimiento público y mapas en :8080. Se utiliza la skill local frontend-design, Manrope y los tokens/componentes compartidos. La vista de mapas se integra en la navegación principal; los enlaces anteriores redirigen. [Alcance y capturas](frontend/UNIFICACION.md).

| Comprobación | Resultado |
| --- | --- |
| Compilación normal/local y lint | Correctos; entrada funcional incluida en Vite |
| Unitarios de tema/componentes y HTTP/paginación | **7 + 22 passed** |
| Regresión de navegador del cliente funcional | **10 passed**; reintentos con recarga y cursores conservados |
| Vistas del diseño de referencia | **29 passed** |
| Mapas y controles GPS | **15 passed** |
| Compilación normal sin simulador | **1 passed** |
| Interfaz funcional unificada | **57 passed**, 11.6 s: cinco vistas × ambos temas × cinco anchos, axe, menú/foco/Escape, registro/habilitación, mapa integrado, respuestas tardías y sesión/tema en memoria |
| Flujo de navegador con API real | **1 passed**, 44.6 s: abrir mapas desde los pedidos reales de repartidor/comercio y seguimiento público, emitir el recorrido y completar la entrega |

Se inspeccionaron las capturas de comercio y repartidor y se corrigió el desborde del formulario móvil causado por el ancho mínimo de la tabla. Se protegió la transición al mapa frente a respuestas pendientes de la vista anterior. La sesión y el tema se comparten sin depender de abrir otra pestaña. Las capturas de vistas generales usan fixtures explícitos; las de mapas provienen del smoke real. CI detectó y permitió corregir que el proxy Vite capturaba `api.js`: ahora solo se proxifica `/api/`. La suite de mapas apunta deliberadamente a un backend inaccesible y usa exclusivamente la API interceptada. Se conservaron endpoints, persistencia y transacciones; no se repitieron pruebas backend o de carga local porque esta revisión modifica solo frontend, su servidor y documentación. CI ejecuta también el backend. No se realizó revisión humana con lector de pantalla ni GPS físico de teléfono.

## SPEC-08 — ubicación y seguimiento — 2026-11-15

GEO-00 a GEO-05 implementadas. [Guía y limitaciones](geo/README.md), [verificación antes de implementar](geo/GEO-00.md), capturas reales de [comercio claro](evidencias/spec08/comercio-claro-1440.png) y [destinatario oscuro móvil](evidencias/spec08/destinatario-oscuro-390.png).

| Comprobación ejecutada | Resultado |
| --- | --- |
| MiniStack 1.5.36 / Redis 7.4.2, antes de implementar | DescribeTable ACTIVE, get_routes 30, Lambda Python 3.12, EVAL correcto y **2 flujos HTTP reales aprobados** |
| Suite Python moto/fakeredis con Lua | **126 passed, 17 deselected**, 15.40 s |
| Integraciones GPS + flujos API existentes | **4 passed**, 12.56 s: permisos, expiración/limpieza, concurrencia Lua y TTL real; API Gateway → Lambda → DynamoDB/Redis |
| `build`, `build:local`, `lint` | Correctos: compilación normal y local, TypeScript y ESLint |
| Unitarios frontend existentes y diseño | **22 + 7 passed** |
| Navegador de frontend existente y FE-01 | **10 + 29 passed** |
| Mapas y controles GPS con API interceptada | **15 passed**: claro/oscuro, 360/390/768/1440, axe, consentimiento, GPS denegado, sesión, simulador, datos obsoletos y fallos Redis/tiles |
| Compilación normal sin simulador | **1 passed**: solo GPS optativo, sin controles de simulación |
| Navegador con API real | **1 passed**, 42.3 s: ocho puntos por HTTP, mapa de comercio/destinatario, fin del recorrido y eliminación al entregar; datos de prueba limpiados |

Se actualizó el stack local y se reinició el proxy para aplicar redacción de tokens. El smoke real no intercepta API ni tiles; las capturas muestran el mapa recibido de OSM. Las suites automáticas no prueban un sensor GPS físico ni certifican accesibilidad humana. Redis/DynamoDB no son una transacción distribuida; las lecturas comprueban META, hay revalidación tras escribir y TTL de respaldo. No se repitieron carga 10k ni carrera de 100 aceptaciones porque no se cambió la asignación transaccional. CI incluye las suites GPS simuladas y la exclusión del simulador; la integración real se selecciona explícitamente.

## Ajuste de selectores FE-01 — 2026-11-15

Se asignan explícitamente fondo y texto de las opciones nativas a los tokens del tema, evitando texto claro sobre el fondo blanco del popup del sistema. Aplica a Apariencia, Vista y Estado. Se añaden dos pruebas de contraste calculado de todas las opciones y selección con teclado, en claro y oscuro. Resultado: **29 pruebas de navegador aprobadas**; compilación y lint correctos. La presentación final del popup nativo puede variar según navegador y sistema operativo.

## Diseño frontend v2.1 — FE-00/FE-01 — 2026-11-15

Prototipo independiente con datos simulados; pendiente revisión visual del usuario. [Decisiones](frontend/FE-00-DISENO.md) y [capturas/flujo](frontend/FE-01-REVISION.md).

| Comprobación | Resultado |
| --- | --- |
| `npm run build` y `npm run lint` | Correctos: TypeScript, compilación Vite y ESLint |
| `npm run test:design` | **7 passed**: tema, sistema, almacenamiento y primitivas |
| `npm run test:design:e2e` | **27 passed**, Chromium: matriz de 20 vistas/tamaños/temas, axe, sin overflow, teclado, formularios, estados y tema inicial |
| `npm test` | **22 passed**, regresión HTTP y paginación existente |
| `npm run test:e2e` | **10 passed**, regresión del frontend funcional en escritorio/móvil |

Se inspeccionaron capturas de comercio y repartidor; se corrigieron contraste del texto secundario claro y desborde móvil, y se mantuvo la acción del repartidor por encima de la navegación inferior. Se guardan cuatro PNG en `docs/evidencias/frontend-fe01/`. Los tests del prototipo rechazan llamadas externas/API. Las comprobaciones de accesibilidad son automáticas y de teclado; no se ejecutó revisión humana con lector de pantalla. No se repitieron backend, smoke real ni rendimiento porque esta entrega no modifica esos componentes. CI incorpora compilación, lint y ambas suites nuevas. FE-02 e integración real pendientes.

## SPEC-07 — fiabilidad del frontend — 2026-11-15

| Comprobación ejecutada | Resultado |
| --- | --- |
| `npm test`, desde frontend | **22 passed**: HTTP, reintentos, reautenticación y paginación |
| `npm run test:e2e` con Chromium | **10 passed**: cinco escenarios, repetidos en escritorio y viewport/touch móvil; 3.2 s |
| `npm run test:smoke` contra web/API real | **1 passed**, 4.1 s: health, zonas y login hasta el formulario de alta, sin crear perfiles/pedidos |
| Suite unitaria Python | **100 passed, 15 deselected**, 11.85 s |
| `tests/integration/test_api_flow.py` | **2 passed**, 7.32 s; flujo HTTP real existente después de reprovisionar |
| `scripts.provision` | Stack local actualizado; `/api/v1/zones` dejó de devolver el 404 del despliegue anterior |

Los casos de fallo del navegador usan API interceptada: JSON truncado después de 201, aborto de red y 503, recarga, formulario reenviado con la misma clave y una sola creación lógica en la simulación. La comprobación real no simula esas fallas ni acredita por sí sola las carreras del backend. No se repitieron carga de 10k ni las 100 aceptaciones porque no cambió su implementación.

Se añadieron job frontend de CI, lock de Playwright y documentación de reintentos y almacenamiento. Las dependencias son solo de desarrollo; la SPA sigue servida sin compilación. El almacenamiento bloqueado solo conserva el respaldo en memoria, y no se ofrece exclusión entre pestañas. Evidencias históricas de SPEC-00–06 a continuación.

## Frontend — 2026-11-13

SPA sin dependencias en `frontend/` servida por `web` (proxy same-origin hacia API Gateway). Verificada en el navegador integrado contra MiniStack:
- Comercio `tienda_demo`: publicó un pedido (tras corregir el `step` del campo de tarifa y el patrón del usuario, que el navegador rechazaba), y abrió el detalle con su historial y enlace de seguimiento.
- Repartidor `rep_demo1`: quedó conectado (heartbeat), aceptó, recogió y entregó.
- Seguimiento público: mostró los cuatro pasos sin direcciones.
- Comercio otra vez: estadística «1 entregado, $9.500 Desde DynamoDB» y, al repetir la consulta, «Desde Redis».
- Modo claro y vista de 375 px de ancho sin desbordes horizontales; modo oscuro según el sistema.

## SPEC-06 — calidad y rendimiento — 2026-11-13

| Comprobación ejecutada | Resultado |
| --- | --- |
| `python -m scripts.benchmark --orders 10000 --samples 100` | Correcto; [informe](informe-calidad.md) y [datos](evidencias/benchmark-10k.json) |
| Query AP05 frente a Scan equivalente | 25 frente a 20 017 ítems leídos; p50 349 ms frente a 1 444 ms en MiniStack |
| Caché de estadísticas | miss p50 2,36 ms, hit p50 0,17 ms, TTL 300 s |
| 100 aceptaciones concurrentes | 1 ganador, 99 × 409 `ORDER_ALREADY_ASSIGNED` |
| Suite completa | 115 passed |

## SPEC-05 — Dispatch, Availability, Tracking y Analytics — 2026-11-13

Lambdas `flashdelivery-dispatch`, `-availability`, `-tracking` y `-analytics` desplegadas; las 27 operaciones del OpenAPI quedan servidas por API Gateway.

| Comprobación ejecutada | Resultado |
| --- | --- |
| `tests/test_http_dispatch_flow.py` | **4 passed** |
| `tests/integration/test_api_flow.py` | **2 passed**: SPEC-04 y ciclo completo SPEC-05 por HTTP real |
| Suite completa desde cdk-dev | **115 passed**, 84 s |

## SPEC-04 — primer flujo vertical por HTTP — 2026-11-13

Lambdas `flashdelivery-identity`, `-stores`, `-couriers` y `-orders` desplegadas desde el ZIP con `scripts.provision`; rutas de API Gateway generadas desde `infra/routes.py`.

| Comprobación ejecutada | Resultado |
| --- | --- |
| Prueba de humo HTTP contra el gateway de MiniStack | Zonas, dev-login, alta y habilitación de comercio, creación con token, detalle, listado y 401 correctos; MiniStack entrega `pathParameters` y `rawPath` sin prefijo de etapa |
| `tests/test_http_base_flow.py` | **6 passed** |
| `tests/integration/test_api_flow.py` | **1 passed** (flujo completo por HTTP) |
| Suite completa desde cdk-dev | **110 passed**, 50.1 s |

## SPEC-03 — contratos, API y autorización — 2026-11-13

Contrato HTTP v1 en `docs/api/openapi.json` (27 operaciones), registro único de rutas en `app/infra/routes.py`, identidad local con tokens HMAC y capa HTTP compartida (`shared/http.py`). `docker-compose.yml` monta `docs/` en solo lectura dentro de cdk-dev para que las pruebas de contrato lean el OpenAPI.

| Comprobación ejecutada | Resultado |
| --- | --- |
| `tests/test_api_contract.py` | **13 passed**: OpenAPI = registro de rutas, `$ref` resueltos, seguridad por operación, tokens, errores, límite de solicitudes |
| CI de GitHub Actions del PR de SPEC-02 | Correcto; PR fusionado en develop con autorización del usuario |

## SPEC-02 — transacciones, estados e idempotencia — 2026-11-13

Implementados los comandos T1–T5 y el procedimiento excepcional FAILED como casos de uso, sin HTTP: `orders.service.create_order`, `dispatch.service.accept_order`, `pick_up_order`, `deliver_order`, `cancel_order` y `fail_order`. Cada uno lee con consistencia fuerte, valida reglas para responder errores claros y confirma META, evento, vistas, ACTIVE, agregado y registro idempotente en un único `TransactWriteItems` mediante `shared/storage/transactions.run_command`.

| Comprobación ejecutada | Resultado |
| --- | --- |
| Sonda de MiniStack 1.5.36 | `CancellationReasons` por acción, `ADD`/`if_not_exists` dentro de transacciones y `REMOVE` de claves GSI soportados |
| `tests/test_commands.py` (moto/fakeredis) | **18 passed** |
| `tests/integration/test_concurrency.py` (MiniStack, hilos) | **2 passed**: 100 aceptaciones concurrentes → 1 ganador; 1 repartidor vs 2 pedidos → máximo 1 |
| Suite completa desde cdk-dev | **90 passed**, 45.8 s; 77 unitarios y 13 integraciones |

Decisiones: las transiciones sustituyen META y vistas con `expected_version` (la versión leída implica el estado leído); el agregado mensual usa un `Update` con `ADD` para que entregas simultáneas del mismo comercio no compitan por una versión, y no se cuenta dos veces porque la condición de estado del pedido va en la misma transacción. Ante `TransactionConflict` el comando relee y reintenta hasta 3 veces; ante `ConditionalCheckFailed` traduce el motivo de la acción fallida a un código estable (`ORDER_ALREADY_ASSIGNED`, `COURIER_HAS_ACTIVE_ORDER`, `ORDER_CHANGED`, etc.). Antes de interpretar una cancelación se consulta el registro idempotente: si otra solicitud con la misma clave confirmó primero, se devuelve su resultado.

El token de seguimiento se deriva con HMAC (`TRACKING_TOKEN_KEY`) del ID del pedido: un reintento de creación devuelve el mismo token sin guardar el secreto en claro. La invalidación de la caché de estadísticas ocurre después del commit y un fallo de Redis no revierte la entrega.

## SPEC-01 — modelo de persistencia

Implementados los nueve tipos de ítem de la tabla única, claves/índices canónicos, consultas AP01–AP12, cursores, rangos, condiciones y descriptores de escritura por módulo. El [modelo detallado](data-model/README.md) incluye el [catálogo JSON](data-model/catalogo-items.json). El token de seguimiento localiza el pedido por ID y verifica el secreto por hash antes de leer eventos.

| Comprobación ejecutada | Resultado |
| --- | --- |
| Unitarios en contenedor `--network none` | **59 passed, 11 deselected**, 6.74 s |
| Suite completa desde cdk-dev después de reprovisionar | **70 passed**, 6.99 s; 59 unitarios y 11 integraciones |
| `python -m scripts.seed_data --namespace SEED_spec01`, repetido dos veces | 43 ítems por ejecución; escrituras sobre las mismas claves sintéticas |
| `python -m scripts.seed_data --namespace SEED_spec01 --clean` | Limpieza por claves exactas; sin Scan ni vaciado global de Redis |
| `python -m scripts.provision` desde cdk-dev | Nuevo ZIP publicado y stack actualizado; health/readiness continúan operativos |
| pip check, compileall, Compose config, enlaces locales y catálogo JSON | Correctos |

Los tests AP01–AP12 con moto/fakeredis registran las llamadas para comprobar PK/SK, índices, expresiones, consistencia fuerte/eventual y paginación. Cubren cursores de otra consulta, fechas inclusivas con empate de timestamp, límites, campos reservados mediante aliases, ausencia de Scan/FilterExpression, TTL/miembros caducados/JSON corrupto en Redis y seguimiento sin datos privados.

La nueva integración crea namespace UUID sobre MiniStack/Redis, ejercita los doce accesos, espera convergencia GSI y verifica reemplazo transaccional de META/evento/vistas/ACTIVE, retirada del índice abierto y rechazo condicional sin nueva mutación. Limpia tanto los datos del seed como las claves adicionales de la prueba.

La documentación y README se actualizaron con el estado de persistencia; se retiró del README la explicación del origen de la organización. No se implementaron endpoints ni se acreditan todavía concurrencia de negocio, autorización HTTP o resolución duradera de reintentos: corresponden a SPEC-02/03/05. Cursores sin firma y tamaños JSON conservadores se documentan expresamente.

## Reorganización según el ejemplo del curso — 2026-11-12

Revisado nuevamente `bd_no_sql` en el commit `835ada8aa75f243b8bc2f5a80fa8cd37519ea5f8`, incluyendo fixtures y tests de caché. La estructura actual es `app/infra`, `app/lambdas`, `app/layers/dependencias`, `app/tests` y `app/scripts`. Los comandos de apartados anteriores corresponden al historial de la organización previa; usar los del README y [guía local](ENTORNO_LOCAL.md).

| Comprobación ejecutada | Resultado |
| --- | --- |
| `docker compose up -d --build --wait` | Tres contenedores activos; app montada en `/app`; dependencias de tests fijadas |
| `python -m scripts.provision` desde cdk-dev | Despliegue actualizado con `main` y nuevo ZIP lambdas/; tabla e API conservadas |
| Unitarios con `docker run --network none` y app montada | **24 passed, 10 deselected**, 4.69 s; sin red y sin acceso a los servicios de datos |
| Unitarios moto ejecutados antes de integraciones, mismo proceso | **15 passed**, 0.91 s; los fixtures restauran el entorno y las integraciones siguen funcionando |
| Suite completa desde cdk-dev con el lock definitivo | **34 passed**, 5.20 s: 24 unitarios y 10 integraciones |
| Persistencia desde `app/scripts` y nueva ejecución de integraciones sin reprovisionar | Marcadores conservados y limpiados; integraciones aprobadas después del reinicio |
| `python -m pip check` | No broken requirements found |
| compileall, Compose config, enlaces Markdown y diff check | Correctos |

Nuevas pruebas: cache JSON/miss/TTL/delete/Redis caído, health con moto/fakeredis, consultas GSI y rollback en moto, bloqueo de acceso a otra tabla y contenido del ZIP sin dependencias de desarrollo. Los tests de integración reales anteriores se conservaron bajo `app/tests/integration`.

Se añadió GitHub Actions para unitarios en ramas feature y PRs a develop; la ejecución remota se consulta en el PR. El comando normal `pytest tests/ -v` selecciona unitarios, como en el curso; seleccionar explícitamente `-m integration` para los reales.

## Incremento 0 — ejecución directa del 2026-11-12

La siguiente evidencia corresponde a esta sesión, con MiniStack `1.5.36`, Redis `7.4.2-alpine` y cdk-dev Python 3.12/Node 22. Los apartados posteriores conservan el historial anterior y sus restricciones, que no describen esta ejecución.

| Comprobación | Resultado |
| --- | --- |
| `docker compose --profile dev up -d --build --wait` | Imagen construida con restricciones de versiones; tres servicios en ejecución |
| `docker compose exec -T cdk-dev python -m scripts.provision` | ZIP con dependencias publicado en S3 local y CloudFormation aplicado sin bootstrap CDK |
| `docker compose exec -T cdk-dev python -m pytest -q` | **20 passed**, 5.43 s |
| `docker compose exec -T cdk-dev python -m pip check` | No broken requirements found |
| `.venv/bin/python -m scripts.check_persistence` | Marcadores DynamoDB y Redis conservados después de reinicio ordenado y limpiados; evidencia `.local/persistence.json` |
| Suite inmediatamente después del reinicio, sin reprovisionar | **20 passed**, 5.50 s; rutas, Lambda ZIP y artefactos siguen utilizables |
| Compose config, compileall y diff check | Correctos |

Las integraciones comprueban escritura/lectura, GSIs, commit/rollback, Redis y API Gateway. `/api/v1/ready` ejecuta el handler empaquetado que importa adaptadores compartidos y consulta DynamoDB/Redis. Las pruebas unitarias adicionales verifican 503 ante cada dependencia caída y cierre de clientes; no se presentó esa simulación como prueba de caída real del contenedor.

La primera invocación empaquetada detectó rechazo de la credencial ficticia inyectada por MiniStack (`000000000000`). Se verificó la implementación instalada `ministack/core/lambda_runtime.py`, se admitió únicamente ese valor adicional y se retiraron variables reservadas del entorno declarativo Lambda. Los endpoints siguen restringidos y los clientes conservan credenciales explícitas test/test.

Persistencia verificada para apagado ordenado, no para pérdida abrupta del proceso. Sin lógica de negocio todavía: la suite no acredita aceptación competitiva ni aislamiento IAM equivalente a AWS. Las versiones Python están fijadas sin hashes de wheels; las imágenes conservan tags sin digest.

## Historial — 2026-11-10

Repositorio inspeccionado: inicialmente solo `README.md` con el título `flash-delivery`.
No había `.pln`, contratos, código, frontend ni instrucciones AGENTS.md en el árbol.

| Comprobación ejecutada | Resultado |
| --- | --- |
| `docker compose config --quiet` | Correcto |
| `python3 -m compileall -q backend scripts infrastructure` | Correcto |
| `git diff --check` | Correcto |
| Invocación directa de `backend.health.handler` y validación del JSON | Correcto |
| `docker info`, `docker image ls` | Bloqueados: permission denied en docker.sock |
| `docker compose up -d --wait` | Bloqueado por acceso al daemon Docker |
| Creación `.venv` | Correcta |
| Instalación pip de dependencias | Bloqueada: resolución DNS de pypi.org |
| `.venv/bin/python -m pytest -m 'not integration'` | No ejecutable: pytest no está instalado |
| Servidor alternativo y solicitud HTTP local | Bloqueados: socket TCP devuelve Operation not permitted |
| Síntesis CDK, creación CloudFormation, Redis, DynamoDB y HTTP por API Gateway | Pendientes: faltan dependencias y acceso a Docker |

No se ejecutaron tests con mocks para presentar las integraciones como comprobadas.
No se crearon recursos externos. La suite de integración NO se considera aprobada.
Los criterios de aceptación requieren una ejecución posterior en un host habilitado.

## Revisión posterior en la misma sesión

Las dependencias ya están instaladas en `.venv` mediante la terminal del usuario.

- Pytest unitario: **7 passed, 7 deselected**.
- Suite completa: **7 failed, 7 passed, 2 errors**. Integraciones bloqueadas por
  permisos del socket Docker/TCP; salud API también falla por ausencia de
  `.local/outputs.json` (provisionamiento pendiente). Los dos errores de teardown
  son intentos de limpieza DynamoDB bloqueados por la misma restricción TCP.
- Síntesis CDK: correcta con `JSII_RUNTIME_PACKAGE_CACHE=disabled`, necesario solo
  aquí porque la caché bajo `/home` tiene un ancestro con propietario no admitido
  por JSII. No se cambiaron permisos del host ni se desactivaron validaciones.
- Inspección de la plantilla generada: tabla, GSIs, PAY_PER_REQUEST y ruta health
  correctos. Esto no acredita que CloudFormation la haya aplicado.
- JSII advierte que Node 26 no fue probado; usar Node 22 como indica el README.

## Corrección de dependencia de bootstrap

La ejecución compartida por el usuario confirmó contenedores sanos, salud de
MiniStack y Redis: suite anterior con 10 aprobadas, 4 fallidas y 2 errores de
limpieza. CreateStack falló antes de crear recursos porque el sintetizador CDK
predeterminado añadió un parámetro SSM `/cdk-bootstrap/hnb659fds/version`.

Se corrigió la definición con `BootstraplessSynthesizer`, coherente con la Lambda
inline y la ausencia de assets. Se añadió una prueba de regresión que sintetiza
la plantilla y rechaza parámetros/reglas de bootstrap, referencias SSM de
bootstrap y código Lambda alojado en S3.

Validación posterior: **8 passed, 7 deselected**. No se pudo aplicar desde esta
sesión por la restricción del socket Docker/TCP; pendiente repetir en la terminal
del usuario `scripts.provision` y después la suite completa. El aviso de Node 26
es independiente del fallo de bootstrap; se recomienda Node 22.

## Validación confirmada por el usuario

Tras la corrección de BootstraplessSynthesizer, el usuario confirmó que el
provisionamiento y la suite completa finalizaron sin fallos. Esta confirmación
proviene de su terminal, no de una ejecución independiente de esta sesión. No se
adjuntó salida final ni conteo; no se atribuye una cifra exacta. La persistencia
tras reinicio y la concurrencia de aceptación de negocio no forman parte de esa suite.
