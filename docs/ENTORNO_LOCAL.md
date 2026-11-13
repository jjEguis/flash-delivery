# Entorno local y paquete Lambda

## Inicio con Docker

Desde la raíz, copiar `.env.example` a `.env` si aún no existe. Ajustar `DEV_UID` y `DEV_GID` al usuario del host cuando sean distintos de 1000; evitan archivos del workspace propiedad de root.

```bash
docker compose --profile dev up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m pytest -q
```

El perfil `dev` incorpora Python 3.12, Node 22 y dependencias CDK/pytest; los dos servicios de datos siguen disponibles sin ese perfil. Se usa la API Python de CDK: no hace falta instalar npm, AWS CLI, cdklocal ni ejecutar bootstrap. El contenedor no tiene acceso al socket Docker. La suite comprueba salud por red cuando corre dentro de cdk-dev y estado de contenedores cuando corre en el host.

Las versiones Python directas y transitivas probadas están en `requirements-dev.lock` y `backend/requirements-runtime.lock`, usados como restricciones por pip. Actualizar y validar ambos al cambiar dependencias. Las imágenes base usan tags por versión; no están fijadas por digest y los locks no incluyen hashes de wheels.

## Empaquetado y despliegue

`scripts.provision` instala las dependencias runtime fijadas con wheels para Python 3.12/Linux x86_64 en una carpeta temporal, incorpora `backend` sin tests ni `.env` y genera `.local/artifacts/backend.zip`. Las entradas tienen fecha y permisos estables; el SHA-256 del ZIP forma la clave de S3. Mismo contenido produce la misma clave.

Antes de aplicar CloudFormation, el script crea si falta el bucket local `flashdelivery-local-assets` y publica el ZIP. Este bucket es preparación explícita de artefactos, fuera del stack de aplicación; no es un bootstrap CDK. Los recursos de aplicación siguen definidos por CDK. Las versiones anteriores de ZIP se conservan; no hay limpieza automática de artefactos.

La síntesis aislada sirve para inspeccionar la plantilla, sin red. Su clave predeterminada `backend/not-built.zip` es un marcador: para desplegar usar `scripts.provision`, que construye/publica el paquete e introduce la clave real.

La función `flashdelivery-readiness`, con handler `backend.readiness.handler`, importa los adaptadores compartidos y comprueba `DescribeTable` en DynamoDB y `PING` en Redis. Su rol declara permiso DescribeTable únicamente para la tabla del proyecto. El ejecutor local de MiniStack no acredita aislamiento ni aplicación de permisos equivalentes a AWS.

| Ruta | Resultado |
| --- | --- |
| `/health` | Sonda de ejecución original, sin dependencias |
| `/api/v1/health` | Alias versionado de la misma sonda |
| `/api/v1/ready` | Lambda empaquetada; 200 con ambas dependencias disponibles, 503 si falla alguna |

Las URLs completas se guardan en `.local/outputs.json`. Desde el host construirlas con `http://127.0.0.1:<puerto>/_aws/execute-api/<ApiId>/local`; los outputs producidos dentro de cdk-dev usan `http://ministack:4566`, accesible desde la red Compose.

Dentro de Lambda, DynamoDB usa `http://ministack:4566` y Redis `redis:6379`. MiniStack 1.5.36 sin AUTH inyecta `000000000000` como access key: se acepta ese valor ficticio además de `test`; el secreto admitido sigue siendo `test`. Los clientes construyen su sesión explícita `test/test` y solo admiten endpoints locales. Las variables reservadas AWS de identidad/región se dejan al runtime.

Referencias: [emulador MiniStack](https://github.com/ministackorg/ministack) y [paquetes ZIP de Python Lambda](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html). La compatibilidad de esta versión se verifica con la suite del proyecto, no solo con el catálogo del emulador.

## Persistencia con reinicio

Esta prueba se ejecuta desde el host, necesita las dependencias Python instaladas y acceso a Docker. Reinicia MiniStack y Redis; ejecutar cuando no haya otra suite usando los servicios.

```bash
.venv/bin/python -m scripts.check_persistence
```

Escribe marcadores UUID en ambos almacenes, reinicia conservando volúmenes, espera salud, comprueba ambos y limpia únicamente sus marcadores. Registra resultado en `.local/persistence.json`. No borra ni reprovisiona la tabla para ocultar una pérdida. Verifica apagado ordenado; no simula corte eléctrico ni borrado de volúmenes.

Después del reinicio se puede repetir la suite para comprobar también API Gateway, Lambda empaquetada y artefacto S3 persistidos. No se ejecutan reinicios dentro de pytest.

## Alternativa desde el host

El flujo anterior del README con venv sigue disponible. En hosts donde JSII rechace la propiedad de la caché, anteponer `JSII_RUNTIME_PACKAGE_CACHE=disabled` a la invocación de `scripts.provision`; el contenedor ya lo configura. Preferir el contenedor si las versiones de Python/Node del host difieren de las probadas.
