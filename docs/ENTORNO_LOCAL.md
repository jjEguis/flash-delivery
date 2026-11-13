# Entorno local y paquete Lambda

## Inicio con Docker

Desde la raíz, copiar `.env.example` a `.env` si aún no existe. Ajustar `DEV_UID` y `DEV_GID` al usuario del host cuando sean distintos de 1000; evitan archivos del workspace propiedad de root.

```bash
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m pytest tests/ -v
```

El servicio `cdk-dev` incorpora Python 3.12, Node 22 y dependencias CDK/pytest; los tres contenedores arrancan con el comando normal del curso. Se usa la API Python de CDK: no hace falta instalar npm, AWS CLI, cdklocal ni ejecutar bootstrap. El contenedor no tiene acceso al socket Docker. Las integraciones comprueban salud por red dentro de cdk-dev y estado de contenedores cuando corren en el host; los unitarios usan mocks.

Las versiones Python directas y transitivas probadas están en `app/requirements.lock` y `app/layers/dependencias/requirements.lock`, usados como restricciones por pip. Actualizar y validar ambos al cambiar dependencias. Las imágenes base usan tags por versión; no están fijadas por digest y los locks no incluyen hashes de wheels.

## Empaquetado y despliegue

`scripts.provision` instala las dependencias runtime fijadas con wheels para Python 3.12/Linux x86_64 en una carpeta temporal, incorpora `app/lambdas` sin tests ni `.env` y genera `app/.local/artifacts/lambdas.zip`. Las entradas tienen fecha y permisos estables; el SHA-256 del ZIP forma la clave de S3. Mismo contenido produce la misma clave.

Antes de aplicar CloudFormation, el script crea si falta el bucket local `flashdelivery-local-assets` y publica el ZIP. Este bucket es preparación explícita de artefactos, fuera del stack de aplicación; no es un bootstrap CDK. Los recursos de aplicación siguen definidos por CDK. Las versiones anteriores de ZIP se conservan; no hay limpieza automática de artefactos.

La síntesis aislada sirve para inspeccionar la plantilla, sin red. Su clave predeterminada `lambdas/not-built.zip` es un marcador: para desplegar usar `scripts.provision`, que construye/publica el paquete e introduce la clave real.

La función `flashdelivery-readiness`, con handler `lambdas.readiness.handler.main`, importa los adaptadores compartidos y comprueba `DescribeTable` en DynamoDB y `PING` en Redis. Su rol declara permiso DescribeTable únicamente para la tabla del proyecto. El ejecutor local de MiniStack no acredita aislamiento ni aplicación de permisos equivalentes a AWS.

| Ruta | Resultado |
| --- | --- |
| `/health` | Sonda de ejecución original, sin dependencias |
| `/api/v1/health` | Alias versionado de la misma sonda |
| `/api/v1/ready` | Lambda empaquetada; 200 con ambas dependencias disponibles, 503 si falla alguna |

Las URLs completas se guardan en `app/.local/outputs.json`. Desde el host construirlas con `http://127.0.0.1:<puerto>/_aws/execute-api/<ApiId>/local`; los outputs producidos dentro de cdk-dev usan `http://ministack:4566`, accesible desde la red Compose.

Dentro de Lambda, DynamoDB usa `http://ministack:4566` y Redis `redis:6379`. MiniStack 1.5.36 sin AUTH inyecta `000000000000` como access key: se acepta ese valor ficticio además de `test`; el secreto admitido sigue siendo `test`. Los clientes construyen su sesión explícita `test/test` y solo admiten endpoints locales. Las variables reservadas AWS de identidad/región se dejan al runtime.

Referencias: [emulador MiniStack](https://github.com/ministackorg/ministack) y [paquetes ZIP de Python Lambda](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html). La compatibilidad de esta versión se verifica con la suite del proyecto, no solo con el catálogo del emulador.

## Persistencia con reinicio

Esta prueba se ejecuta desde el host, necesita las dependencias Python instaladas y acceso a Docker. Reinicia MiniStack y Redis; ejecutar cuando no haya otra suite usando los servicios.

```bash
cd app
../.venv/bin/python -m scripts.check_persistence
```

Escribe marcadores UUID en ambos almacenes, reinicia conservando volúmenes, espera salud, comprueba ambos y limpia únicamente sus marcadores. Registra resultado en `app/.local/persistence.json`. No borra ni reprovisiona la tabla para ocultar una pérdida. Verifica apagado ordenado; no simula corte eléctrico ni borrado de volúmenes.

Después del reinicio se puede repetir la suite para comprobar también API Gateway, Lambda empaquetada y artefacto S3 persistidos. No se ejecutan reinicios dentro de pytest.

## Alternativa desde el host

Instalar `app/requirements.txt` en el venv y ejecutar los módulos desde `app/`, como muestra el README. En hosts donde JSII rechace la propiedad de la caché, anteponer `JSII_RUNTIME_PACKAGE_CACHE=disabled` a la invocación de `scripts.provision`; el contenedor ya lo configura. Preferir el contenedor si las versiones de Python/Node del host difieren de las probadas.

## Estructura y pruebas del curso

Se revisó el [repositorio bd_no_sql](https://gitlab.com/caov_unimag/bd_no_sql) en el commit `835ada8aa75f243b8bc2f5a80fa8cd37519ea5f8`: README, Dockerfile, Compose, cdk.json, infra, layers y tests. La estructura de app reproduce sus directorios principales y separa el entry point de CDK de la clase del stack. cdk-dev monta `./app:/app` y trabaja en `/app`.

El comando del ejemplo `python -m pytest tests/ -v` ejecuta unitarios por defecto. `-m integration` selecciona las integraciones, y `-m 'integration or not integration'` ejecuta todo. Los fixtures compartidos crean DynamoDB en moto y Redis en fakeredis; el adaptador acepta un cliente inyectado para no apuntar al emulador. El bloqueo de sockets detecta accesos de red accidentales en unitarios.

La capa se conserva como directorio de dependencias runtime del curso. En MiniStack se incluyen esas dependencias dentro del ZIP, sin crear una Layer que no se haya probado. moto, fakeredis, pytest y CDK solo pertenecen al entorno de desarrollo; la integración inspecciona que no se filtren al ZIP.

El helper de caché está en `app/lambdas/shared/cache.py` para reutilizarlo entre futuros módulos del dominio. Prueba JSON, miss, TTL, invalidación y modo degradado; no hay CRUD genérico de items ni endpoints de negocio todavía.
