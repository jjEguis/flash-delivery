# FlashDelivery

Aplicación de entregas de última milla con DynamoDB (tabla única), Redis, Python, Lambda y API Gateway, ejecutada localmente sobre MiniStack. Los comercios publican pedidos, los repartidores de la zona compiten por aceptarlos y una transacción condicional garantiza que solo uno gane. El destinatario sigue su pedido con un enlace seguro.

Estado: SPEC-00 a SPEC-06 implementadas, con API HTTP completa (27 operaciones), interfaz web y evidencias de calidad. Consultar [especificaciones](docs/specs/README.md) y [validación](docs/validation.md).

```text
flash-delivery/
├── docker-compose.yml            # cdk-dev, MiniStack, Redis y web
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
│   │   ├── analytics/            # estadística mensual con Cache-Aside
│   │   └── shared/               # HTTP, errores, almacenamiento, transacciones
│   ├── tests/                    # unitarios moto/fakeredis
│   │   └── integration/          # MiniStack y Redis reales, HTTP y concurrencia
│   └── scripts/                  # provision, seed, demo, benchmark
├── docs/                         # arquitectura, modelo, OpenAPI, specs, evidencias
└── frontend/                     # SPA sin dependencias + servidor con proxy
```

Cada módulo de `app/lambdas/<módulo>/` contiene su repositorio, su servicio de aplicación y un `handler.py` con `main(event, context)`, que se despliega como una Lambda propia.

## Inicio rápido

Requisitos: Docker Engine con Compose v2. No necesitas cuenta ni credenciales AWS.

```bash
cp -n .env.example .env
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m scripts.demo
```

Abre http://127.0.0.1:8080 y entra como:

| Rol | Usuario | Qué puedes hacer |
| --- | --- | --- |
| Comercio | `tienda_demo` | Publicar pedidos, verlos por estado, cancelar, compartir el enlace de seguimiento, ver estadísticas y repartidores conectados |
| Repartidor | `rep_demo1`, `rep_demo2`, `rep_demo3` | Conectarse, aceptar pedidos de la zona, recogerlos y entregarlos |
| Administración | `admin`, código `admin-local` | Habilitar comercios y repartidores, consultar pedidos, marcar FAILED |

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

- Las escrituras de negocio exigen `Idempotency-Key`: repetirla con el mismo cuerpo devuelve el mismo resultado; con otro cuerpo responde 409 `IDEMPOTENCY_CONFLICT`.
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

La integración cubre API Gateway → Lambda empaquetada → DynamoDB/Redis con el ciclo completo de un pedido y 100 aceptaciones concurrentes con un único ganador. GitHub Actions ejecuta los unitarios en cada PR hacia develop.

## Rendimiento y evidencias

```bash
docker compose exec -T cdk-dev python -m scripts.benchmark --orders 10000
```

Carga pedidos sintéticos y mide los patrones de acceso frente a un Scan, la caché de Redis, la concurrencia y la API; resultados y límites del emulador en el [informe de calidad](docs/informe-calidad.md).

## Modelo de datos

Tabla `FlashDeliveryTable` con `PK`/`SK` y dos GSI dispersos; doce patrones de acceso (AP01–AP12) resueltos con GetItem o Query, sin Scan. Detalle en [modelo de datos](docs/data-model/README.md) y [arquitectura](docs/ARQUITECTURA_GENERAL.md).

```bash
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo          # datos sintéticos
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo --clean  # limpieza por claves
docker compose exec -T cdk-dev python -m scripts.demo --clean                             # quitar perfiles demo
```

## Persistencia y límites

Compose usa volúmenes para MiniStack y Redis (AOF). `docker compose down` conserva los datos; `docker compose down --volumes` los borra y exige reprovisionar. Ningún contenedor se conecta a AWS real ni monta el socket Docker. MiniStack no reproduce el rendimiento ni la consistencia eventual exactos de DynamoDB; ver el informe de calidad.

Documentación: [arquitectura](docs/ARQUITECTURA_GENERAL.md), [entorno y tests](docs/ENTORNO_LOCAL.md), [especificaciones](docs/specs/README.md), [plan](docs/PLAN_DE_TRABAJO.md) y [evidencias](docs/validation.md).
