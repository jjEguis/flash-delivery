# FlashDelivery

Fase 1: estructura de un monolito modular serverless e infraestructura exclusivamente
local. Los módulos están vacíos; no se implementan negocio, autenticación ni frontend.

**Estado:** incremento 0 implementado: entorno `cdk-dev`, Lambda empaquetada con
sus dependencias, health versionado y readiness DynamoDB/Redis. Los módulos de
negocio continúan vacíos. Resultados en [validación](docs/validation.md).

Consultar [arquitectura general](docs/ARQUITECTURA_GENERAL.md),
[especificaciones](docs/specs/README.md) y [plan de trabajo](docs/PLAN_DE_TRABAJO.md).
Para comenzar con los tres contenedores y sin instalar Python/Node en el host:

```bash
docker compose --profile dev up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m pytest -q
```

Detalles de empaquetado, artefactos y reinicio en [entorno local](docs/ENTORNO_LOCAL.md).
Los requisitos e instrucciones siguientes corresponden a la alternativa desde el host.

## Requisitos en Linux

- Docker Engine en ejecución y Docker Compose v2 o posterior, accesibles por tu usuario.
- Python 3.12 o 3.13 con `venv` y pip; Node.js 22 LTS para el motor JSII de CDK.
- Acceso a PyPI y Docker Hub; curl para comprobaciones manuales.
- Puertos locales 4566 y 6379 libres; 8080 solo para la alternativa HTTP.

No necesitas cuenta AWS, AWS CLI, CLI CDK ni credenciales reales.

## Instalación e inicio

Desde la raíz de este repositorio (el subdirectorio `flash-delivery/` si lo clonaste
 dentro del workspace `flash_delivery/`):

```bash
cp -n .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
docker compose config --quiet
docker compose pull
docker compose up -d --wait
.venv/bin/python -m infrastructure.cdk.app
.venv/bin/python -m scripts.provision
.venv/bin/python -m pytest -m 'not integration'
.venv/bin/python -m pytest -m integration
```

`.venv/bin/python -m infrastructure.cdk.app` genera `cdk.out/FlashDeliveryLocal.template.json`
sin contactar AWS, con una clave de paquete de ejemplo. `scripts.provision` construye
y publica el ZIP en S3 local, genera la plantilla con su clave real y la aplica a
CloudFormation en MiniStack, espera el resultado y guarda `.local/outputs.json`.
Puede repetirse para actualizar el stack; una tabla existente fuera de ese stack
no se adopta automáticamente. No se ejecutan `cdk bootstrap` ni `cdk deploy`.

La imagen MiniStack se fija a `1.5.36`, versión encontrada en sus fuentes oficiales;
su ejecución fue confirmada por el usuario en su entorno local. Las dependencias directas Python y la
imagen Redis también tienen versiones fijas. Las dependencias transitivas Python
están fijadas en archivos `.lock`; las imágenes aún no están fijadas por digest.

Los comandos invocan directamente `.venv/bin/python` y funcionan en Bash y Fish,
sin activar el entorno ni instalar paquetes en el Python del sistema. Si prefieres
activarlo, en Fish usa `source .venv/bin/activate.fish`; en Bash usa
`source .venv/bin/activate`. No uses `--break-system-packages`.

## Configuración

Si la terminal ya exporta credenciales AWS reales, abre una terminal sin esas variables: la configuración las rechazará por seguridad.

`.env.example` documenta todas las variables locales. Compose lee `.env` y Python lo
carga sin sustituir variables ya exportadas. `AWS_ENDPOINT_URL` se usa para todos
los clientes AWS (incluidos CloudFormation y DynamoDB); solo permite HTTP con puerto
explícito en `localhost`, `127.0.0.1` o `ministack`. Las credenciales admitidas son
`test`/`test`; se admite también el access key ficticio `000000000000`
inyectado por el runtime MiniStack, manteniendo secreto `test`. Los clientes usan una sesión explícita, sin perfiles ni
proxies. `ENVIRONMENT` debe ser `local`.

Desde el host: endpoint `http://127.0.0.1:4566`, Redis `127.0.0.1:6379`.
Si se añade posteriormente un proceso dentro de la red Compose: endpoint
`http://ministack:4566`, Redis `redis:6379`.
Al cambiar `MINISTACK_PORT`, actualiza también `AWS_ENDPOINT_URL`; `REDIS_PORT`
representa el puerto publicado del host (dentro de Docker sigue siendo 6379).
`CONNECT_TIMEOUT` y `READ_TIMEOUT` se aplican a los clientes. El nombre de tabla
predeterminado es `FlashDeliveryTable`; región `us-east-1`, cuenta emulada `000000000000`.

## Comprobaciones manuales

```bash
docker compose ps
curl --fail http://127.0.0.1:4566/_ministack/health
docker compose exec -T redis redis-cli ping
.venv/bin/python - <<'PY'
from backend.shared.infrastructure.clients import DynamoDBAdapter
adapter = DynamoDBAdapter()
print(adapter.client.describe_table(TableName=adapter.settings.table_name)['Table'])
PY
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from urllib.request import urlopen
url = json.loads(Path('.local/outputs.json').read_text())['HealthUrl']
with urlopen(url, timeout=5) as response:
    print(response.status, response.read().decode())
PY
```

La URL de salud se obtiene tras provisionar:
`http://127.0.0.1:4566/_aws/execute-api/<ApiId>/local/health`.
El cuerpo esperado es:

```json
{"service":"flashdelivery","status":"ok","environment":"local"}
```

## Pruebas

```bash
.venv/bin/python -m pytest -m 'not integration'  # contrato del handler y barreras locales
.venv/bin/python -m pytest -m integration        # requiere Compose sano y provisionamiento
.venv/bin/python -m pytest                       # ambas categorías
```

Las pruebas de integración verifican estado y salud de ambos contenedores, Redis
(PING, TTL, set y sorted set), esquema y facturación DynamoDB, Put/Get/Update,
consultas por GSI1 y GSI2, transacciones exitosas y rollback completo cuando una
condición falla, y GET /health por API Gateway. No se omiten pruebas ante una
funcionalidad incompatible: fallan para hacer visible la limitación. Usan UUID para
sus datos, los limpian al finalizar y no reinician ni vacían los almacenes completos.
Un fallo de limpieza podría dejar elementos `TEST#<uuid>` o claves
`flashdelivery:test:<uuid>` locales. No ejecutes esta suite contra recursos externos.

## Alternativa HTTP explícita

MiniStack documenta la integración API Gateway–Lambda. Si la versión elegida falla,
conserva el error como evidencia de compatibilidad antes de cambiar la infraestructura.
Para verificar el handler de forma independiente:

```bash
.venv/bin/python -m scripts.health_local
# En otra terminal, desde la misma máquina:
curl --fail http://127.0.0.1:8080/health
```

Este servidor usa la biblioteca estándar y el mismo handler, **sin API Gateway ni
Lambda emulados**. No hace pasar la prueba de integración de API Gateway. En el
entorno de creación también estuvo bloqueado por la prohibición de sockets TCP.

## Detener, reiniciar y persistencia

```bash
docker compose stop
# Reiniciar conservando recursos y datos:
docker compose up -d --wait
.venv/bin/python -m scripts.provision
docker compose restart
# Detener y retirar contenedores/red, conservando volúmenes:
docker compose down
# Solo si quieres borrar todos los datos LOCALES de este proyecto:
docker compose down --volumes
rm -rf .local cdk.out
```

Redis usa AOF y un volumen propio. MiniStack utiliza `PERSIST_STATE=1` y `STATE_DIR`
en otro volumen; sus fuentes indican que guarda estado al cerrar y lo restaura al
arrancar. Una terminación abrupta puede perder cambios recientes. Después de borrar
volúmenes debes volver a ejecutar `scripts.provision`. La tabla tiene política RETAIN
al eliminar el stack: borrar solo el stack no constituye un reinicio limpio.

## Estructura y límites

- `backend/modules/`: identity, stores, couriers, orders, dispatch, availability,
  tracking y analytics, solo paquetes vacíos.
- `backend/shared/`: configuración local y adaptadores técnicos reutilizables.
- `backend/health.py`: sonda de ejecución; `backend/readiness.py`: comprobación de DynamoDB/Redis desde ZIP.
- `backend/tests/`: contrato, configuración y comprobaciones de infraestructura real local.
- `infrastructure/cdk/`: tabla única, dos GSIs, roles, Lambdas y HTTP API.
- `docker-compose.yml`: MiniStack y Redis con red, volúmenes y healthchecks; cdk-dev con perfil dev.
- `scripts/`: provisionamiento local y alternativa HTTP explícita.
- `frontend/`: reserva documental para React + Vite.

Las decisiones están en [arquitectura general](docs/ARQUITECTURA_GENERAL.md). Los módulos futuros
usarán sus propios repositorios sobre estos adaptadores y contratos explícitos,
sin importar detalles de MiniStack ni implementaciones internas de otros módulos.

## Compatibilidad y problemas conocidos

El stack usa `BootstraplessSynthesizer`: no requiere el parámetro SSM
`/cdk-bootstrap/hnb659fds/version`. Si una plantilla antigua muestra ese error,
vuelve a ejecutar `.venv/bin/python -m scripts.provision` con el código actualizado;
no necesitas crear parámetros de bootstrap manualmente.

Consulta [la matriz de compatibilidad y fuentes oficiales](docs/ministack.md).
MiniStack es un emulador, no garantiza toda la semántica de AWS. Soporte declarado
no equivale a soporte comprobado. El usuario confirmó provisionamiento y suite completa sin fallos. La persistencia
tras reinicio ordenado se verifica con `scripts.check_persistence`; las carreras de
aceptación de negocio aún requieren implementación y pruebas específicas.

- `permission denied ... docker.sock`: el usuario de la terminal necesita acceso al
  daemon Docker. Este proyecto no modifica permisos del host ni monta el socket.
- `Could not resolve host` o errores pip de DNS: comprobar acceso de la terminal a
  PyPI, GitHub y el registro Docker antes de repetir instalación/pull.
- Si un puerto está ocupado, cambia `.env` y actualiza su endpoint correspondiente.
- Ante fallo CloudFormation, `scripts.provision` muestra eventos; no borra ni recrea
  recursos silenciosamente. Un stack en rollback necesita diagnóstico antes de reintentar.
- El ejecutor Lambda es `local`: ejecuta Python dentro del contenedor MiniStack,
  sin reproducir el aislamiento exacto del runtime Lambda. No precisa imágenes RIE.
- No se comprobó semántica de concurrencia bajo carga: el test de rollback es un
  requisito mínimo de infraestructura, no una prueba de asignación de repartidores.

Siguiente paso: implementar los contratos ejecutables y el primer flujo de publicación,
siguiendo la secuencia de las especificaciones en `docs/specs/`.
