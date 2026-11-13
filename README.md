# FlashDelivery

Aplicación de entregas de última milla con DynamoDB, Redis, Python, Lambda y API Gateway. La infraestructura y el modelo de persistencia están implementados. Los endpoints y casos de uso de negocio siguen pendientes.

Estructura del proyecto:

```text
flash-delivery/
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── app/
│   ├── cdk.json
│   ├── requirements.txt
│   ├── requirements.lock
│   ├── infra/
│   │   ├── app.py
│   │   └── stack.py
│   ├── layers/dependencias/
│   │   ├── requirements.txt
│   │   └── requirements.lock
│   ├── lambdas/
│   │   ├── health/handler.py
│   │   ├── readiness/handler.py
│   │   ├── shared/                  # configuración, adaptadores y caché
│   │   └── orders/, stores/, ...    # repositorios; casos de uso pendientes
│   ├── tests/
│   │   ├── conftest.py              # moto y fakeredis, por prueba
│   │   ├── test_cache.py
│   │   ├── test_dynamodb.py
│   │   ├── test_health.py
│   │   ├── test_unit.py
│   │   ├── test_cdk.py
│   │   └── integration/test_services.py
│   └── scripts/                    # paquete, provisionamiento y persistencia
├── docs/
│   └── specs/
└── frontend/                       # posterior
```

Los handlers exponen `main(event, context)`. Cada funcionalidad concentra su persistencia y sus futuros casos de uso dentro de `app/lambdas/<módulo>/`.

## Inicio con Docker

Requisitos: Docker Engine y Compose v2. No necesitas cuenta ni credenciales AWS reales. Los tres servicios son cdk-dev, MiniStack 1.5.36 y Redis 7.4.2-alpine; cdk-dev incluye Python 3.12 y Node 22.

```bash
cp -n .env.example .env
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
```

Si tu UID/GID no es 1000, configura `DEV_UID` y `DEV_GID` en `.env`. Los puertos predeterminados del host son 4566 y 6379, publicados solo en loopback. Dentro de Compose los endpoints son `http://ministack:4566` y `redis:6379`.

## Tests

Los unitarios se ejecutan dentro de cdk-dev sin usar el emulador ni Redis real:

```bash
docker compose exec -T cdk-dev python -m pytest tests/ -v
# También pueden correr sin arrancar los servicios de datos:
docker compose run --rm --no-deps cdk-dev python -m pytest tests/ -v
```

Los fixtures de moto/fakeredis viven en `app/tests/conftest.py`. El acceso de red de los tests unitarios está bloqueado. No se borran variables del entorno durante la importación de conftest: los cambios de cada fixture se restauran al terminar.

Las integraciones son explícitas y requieren provisionamiento:

```bash
docker compose exec -T cdk-dev python -m pytest tests/ -m integration -v
# Suite completa:
docker compose exec -T cdk-dev python -m pytest tests/ -m 'integration or not integration' -v
```

GitHub Actions ejecuta los tests unitarios en cada PR hacia develop y push a feature. Las integraciones locales verifican DynamoDB, GSIs, commit/rollback, Redis, contenido del ZIP y API Gateway → Lambda. Usan marcadores UUID y limpian únicamente sus datos.

## API local

El provisionamiento guarda `ApiId`, URLs y clave del ZIP en `app/.local/outputs.json`. Desde el host, la base es:

```text
http://127.0.0.1:4566/_aws/execute-api/<ApiId>/local
```

- `GET /health` y `GET /api/v1/health`: sonda de ejecución.
- `GET /api/v1/ready`: comprueba DynamoDB y Redis desde la Lambda empaquetada; devuelve 200 o 503.

Las URLs del archivo de outputs generado dentro de cdk-dev usan el nombre de servicio `ministack`; para llamarlas desde el host usar `127.0.0.1` y el puerto publicado.

## Alternativa desde el host

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r app/requirements.txt
cd app
JSII_RUNTIME_PACKAGE_CACHE=disabled ../.venv/bin/python -m scripts.provision
../.venv/bin/python -m pytest tests/ -v
# Reinicia MiniStack/Redis y verifica marcadores de persistencia:
../.venv/bin/python -m scripts.check_persistence
```

`python -m infra.app`, ejecutado en app/, sintetiza la infraestructura sin red. Para desplegar usar scripts.provision: instala las dependencias runtime del directorio layers, publica el ZIP en S3 local y aplica la plantilla CDK con CloudFormation. La síntesis aislada usa una clave de paquete de ejemplo que no debe desplegarse directamente.

## Persistencia y límites

Compose usa volúmenes para ambos almacenes y AOF para Redis. `docker compose stop` y `docker compose down` conservan volúmenes. `docker compose down --volumes` borra los datos locales y requiere reprovisionar.

Se utiliza MiniStack con provisionamiento CloudFormation local, sin bootstrap CDK. Ningún contenedor monta el socket Docker ni se conecta a AWS real. El apagado ordenado fue probado; un corte abrupto y la concurrencia de negocio siguen fuera de esa evidencia.

Documentación: [arquitectura](docs/ARQUITECTURA_GENERAL.md), [entorno y tests](docs/ENTORNO_LOCAL.md), [especificaciones](docs/specs/README.md), [plan](docs/PLAN_DE_TRABAJO.md) y [evidencias](docs/validation.md).

## Modelo de datos y seed

La tabla única tiene PK/SK y dos GSIs dispersos. Los repositorios cubren AP01–AP12 con lecturas por clave, rangos de fecha y cursores; el seguimiento usa ID más secreto verificable por hash. Detalle en [modelo de datos](docs/data-model/README.md) y [SPEC-01](docs/specs/SPEC-01-DYNAMODB.md).

```bash
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo
# Eliminar únicamente los datos sintéticos de ese namespace:
docker compose exec -T cdk-dev python -m scripts.seed_data --namespace SEED_demo --clean
```

El seed reinicia sus propios datos al repetirse; no se debe usar su namespace para datos de la aplicación. Presencia Redis dura 60 segundos. No se añaden endpoints de negocio en SPEC-01.
