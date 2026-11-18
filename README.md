# FlashDelivery

Aplicación de entregas de última milla con DynamoDB (tabla única), Redis, Python, Lambda y API Gateway, ejecutada localmente sobre MiniStack. Los comercios publican pedidos, los repartidores de la zona compiten por aceptarlos y una transacción condicional garantiza que solo uno gane. El destinatario sigue su pedido con un enlace seguro.

Estado: **SPEC-00 a SPEC-10 fusionadas**. API con 40 operaciones de módulos, interfaz unificada, aprobaciones auditadas, pedidos transaccionales y seguimiento vial local. SPEC-11 actualiza documentación y la guía de estudio.

Para estudiar: **[Documento general de arquitectura](docs/ARQUITECTURA_GENERAL.md)** → [modelo single table](docs/data-model/README.md) → [patrones AP01–AP16](docs/data-access-patterns.md) → [contratos](docs/module-contracts.md). El documento general explica por qué la primary key es `(PK, SK)`, la razón de cada clave e índice, y las garantías con ejemplos. [Índice completo de documentación](docs/README.md).

```text
flash-delivery/
├── docker-compose.yml            # cdk-dev, MiniStack, Redis, OSRM y web
├── Dockerfile
├── .env.example
├── app/
│   ├── infra/                    # stack CDK y registro único de rutas (routes.py)
│   ├── lambdas/
│   │   ├── identity/             # tokens de desarrollo y dev-login
│   │   ├── stores/  couriers/    # perfiles, zonas, habilitación, disponibilidad
│   │   ├── orders/               # crear, consultar y listar pedidos
│   │   ├── dispatch/             # aceptar, recoger, entregar, cancelar, FAILED
│   │   ├── availability/         # presencia en Redis (heartbeat + ZSET)
│   │   ├── tracking/             # seguimiento público por token
│   │   ├── approvals/            # bandejas, detalle y auditoría administrativa
│   │   ├── analytics/            # estadística mensual con Cache-Aside
│   │   └── shared/               # HTTP, errores, almacenamiento, transacciones
│   ├── tests/                    # unitarios moto/fakeredis
│   │   └── integration/          # MiniStack y Redis reales, HTTP y concurrencia
│   └── scripts/                  # provision, seed, demo, benchmark
├── docs/                         # arquitectura, modelo, OpenAPI, specs, evidencias
└── frontend/                     # SPA funcional, diseño React, GPS y proxy
```

Los módulos HTTP se despliegan como Lambdas con `handler.py` y `main(event, context)`. Los módulos de negocio incluyen servicios/repositorios según su necesidad; Identity mantiene sus contratos y tokens. [Colaboración real entre módulos](docs/module-contracts.md).

## Inicio rápido

Requisitos: Docker Engine con Compose v2 y Node 22.12+ con npm para compilar la interfaz. No necesitas cuenta ni credenciales AWS.

```bash
cp -n .env.example .env
docker compose --profile geo-prepare run --rm osm-download
docker compose --profile geo-prepare run --rm osrm-prepare
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m scripts.demo
npm --prefix frontend ci
npm --prefix frontend run build:local
```

Abre http://127.0.0.1:8080 y entra como:

| Rol | Usuario | Qué puedes hacer |
| --- | --- | --- |
| Comercio | `tienda_demo` | Publicar pedidos, verlos por estado, cancelar, compartir el enlace de seguimiento, ver estadísticas y repartidores conectados |
| Repartidor | `rep_demo1`, `rep_demo2`, `rep_demo3` | Conectarse, aceptar pedidos de la zona, recogerlos y entregarlos |
| Administración | `admin`, código `admin-local` | Revisar/aprobar/suspender perfiles, consultar auditoría/pedidos y marcar FAILED |

Cualquier otro usuario puede registrarse como comercio o repartidor; queda pendiente hasta que un administrador lo habilite. El inicio de sesión es un adaptador de desarrollo con tokens HMAC, no apto para producción. Para ver la competencia entre repartidores, abre dos navegadores (o uno en modo incógnito) con repartidores distintos y acepta el mismo pedido.

Si tu UID/GID no es 1000, configura `DEV_UID` y `DEV_GID` en `.env`. Los puertos del host (4566, 6379 y 8080) se publican solo en loopback.

## API

Contrato completo en [`docs/api/openapi.json`](docs/api/openapi.json). El frontend la sirve en el mismo origen (`http://127.0.0.1:8080/api/v1/...`); directamente en MiniStack la base es `http://127.0.0.1:4566/_aws/execute-api/<ApiId>/local`, con `ApiId` en `app/.local/outputs.json`.

```bash
TOKEN=$(curl -s -X POST localhost:8080/api/v1/auth/dev-login -H 'Content-Type: application/json' \
  -d '{"userId":"tienda_demo","role":"STORE"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -X POST localhost:8080/api/v1/orders -H "Authorization: Bearer $TOKEN" -H 'Idempotency-Key: pedido-1' \
  -H 'Content-Type: application/json' -d '{"pickupAddress":"Calle 1","dropoffAddress":"Calle 2","feeMinor":8000}'
```

- Crear y transicionar pedidos exige `Idempotency-Key`: repetir la intención no duplica efectos; con otro contenido responde 409 `IDEMPOTENCY_CONFLICT`. Perfiles/disponibilidad y ubicación tienen mecanismos propios; consultar OpenAPI. El replay puede responder con el estado actual del pedido.
- Errores: `{"error": {"code", "message", "requestId"}}` con 400/401/403/404/409/429/500/503.
- Listados paginados con `limit` (1–100) y `nextCursor` opaco.

## Tests

```bash
# Unitarios (moto/fakeredis, sin red):
docker compose exec -T cdk-dev python -m pytest tests/ -q
# Integración (requiere provision):
docker compose exec -T cdk-dev python -m pytest tests/ -m integration -q
# Todo:
docker compose exec -T cdk-dev python -m pytest tests/ -m 'integration or not integration' -q
```

La integración cubre API Gateway → Lambda empaquetada → DynamoDB/Redis con el ciclo completo de un pedido y 100 aceptaciones concurrentes con un único ganador. GitHub Actions ejecuta los unitarios Python y un job independiente de frontend en cada PR hacia develop.

Pruebas del frontend, desde `frontend/` (Node 22 y Python 3):

```bash
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e          # Chromium de escritorio y vista móvil, con API simulada
npm run test:smoke        # requiere web y API reales provisionadas
```

El navegador conserva las claves de acciones pendientes ante errores de red, respuestas incompletas y fallos transitorios; al recargar puede recuperar la clave si se reenvían los mismos datos. El repartidor dispone de «Cargar más pedidos» y «Cargar más historial», con refresco de las páginas visibles. Alcance y límites en [SPEC-07](docs/specs/SPEC-07-FRONTEND-FIABILIDAD.md).

## Rendimiento y evidencias

```bash
docker compose exec -T cdk-dev python -m scripts.benchmark --orders 10000
```

Carga pedidos sintéticos y mide los patrones de acceso frente a un Scan, la caché de Redis, la concurrencia y la API; resultados y límites del emulador en el [informe de calidad](docs/informe-calidad.md).

## Modelo de datos

Tabla `FlashDeliveryTable` con `PK`/`SK` y dos GSI dispersos; once tipos de ítem y patrones AP01–AP16 documentados. Los accesos operativos DynamoDB usan GetItem/Query; presencia y caché también usan Redis. Scan queda para mantenimiento explícito y benchmark. Detalle en [modelo de datos](docs/data-model/README.md) y [arquitectura](docs/ARQUITECTURA_GENERAL.md).

```bash
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo          # datos sintéticos
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo --clean  # limpieza por claves
docker compose exec -T cdk-dev python -m scripts.demo --clean                             # quitar perfiles demo
```

## Persistencia y límites

Compose usa volúmenes para MiniStack, Redis (AOF) y el extracto procesado de OSRM. `docker compose down` conserva los datos; `docker compose down --volumes` los borra y exige reprovisionar. Ningún contenedor se conecta a AWS real ni monta el socket Docker. MiniStack no reproduce el rendimiento ni la consistencia eventual exactos de DynamoDB; ver el informe de calidad.

Documentación: [arquitectura](docs/ARQUITECTURA_GENERAL.md), [entorno y tests](docs/ENTORNO_LOCAL.md), [especificaciones](docs/specs/README.md), [plan](docs/PLAN_DE_TRABAJO.md) y [evidencias](docs/validation.md).

## Prototipo del nuevo diseño

FE-00/FE-01 de diseño v2.1 están disponibles para revisión visual con datos simulados. Desde `frontend/`: `npm ci` y `npm run dev:preview` (Node 22.12+). Abrir http://127.0.0.1:5173/preview.html. Incluye comercio, repartidor, seguimiento, claro/oscuro y estados de ejemplo. [Guía y capturas](docs/frontend/FE-01-REVISION.md). La aplicación principal ya integra este diseño con la API; preview.html conserva el prototipo como referencia.

## Ubicación, rutas y ETA (SPEC-08 v2)

Desde `frontend/`, ejecutar `npm ci` y `npm run build:local` para habilitar los mapas y el simulador local en la aplicación :8080. Si cambió el backend, ejecutar antes `docker compose up -d --build --wait` y `docker compose exec -T cdk-dev python -m scripts.provision`.

Preparar primero el extracto OSRM como indica el arranque local. Crear un pedido nuevo con puntos de recogida/entrega seleccionados en el mapa, aceptarlo con un repartidor y abrir «Compartir ubicación». Seleccionar el inicio de la demo para recorrer calles, ajustar velocidad, pausar y reanudar. Las rutas cambian al recoger y la ETA es aproximada, sin tráfico real. El comercio abre el mapa desde el detalle; el destinatario, desde su enlace de seguimiento. Solo se comparten posiciones durante entregas activas, con consentimiento, expiración y revocación. `npm run build` excluye los controles de simulación. [Flujo completo, pruebas y límites](docs/geo/README.md).

La aplicación de :8080 utiliza el diseño unificado en acceso, registro, comercio, repartidor, administración, seguimiento y mapas. Comparte Manrope, tokens, navegación y selector Sistema/Claro/Oscuro con la base visual aprobada. Los mapas se abren dentro de la misma interfaz, sin pestañas adicionales. [Alcance y capturas](docs/frontend/UNIFICACION.md).

## Demo guiada de principio a fin (SPEC-09)

En el acceso, abrir «Cómo probar la entrega completa». Para demostrar aprobación, registrar usuarios nuevos de comercio y repartidor, habilitarlos desde una tercera sesión administrativa y continuar con el pedido. Los perfiles de ejemplo ya vienen habilitados. [Pasos, resultados esperados y prueba real](docs/demo/README.md).

## Aprobaciones administrativas (SPEC-10)

En Administración, revisar la bandeja de Comercios o Repartidores, filtrar el estado y abrir «Revisar perfil». Escribir un motivo y confirmar habilitación o suspensión. El detalle muestra el historial de decisiones. Una entrega activa bloquea la suspensión del repartidor. Para instalaciones existentes ejecutar la migración indicada en la [guía administrativa](docs/admin/README.md), después de provisionar el backend.
