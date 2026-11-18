# Entorno local, despliegue y diagnóstico

Revisión: 2026-11-18. Para entender decisiones, leer la [guía general](ARQUITECTURA_GENERAL.md). Para probar una entrega, seguir la [demo guiada](demo/README.md). La fase actual usa MiniStack, no AWS real.

## Requisitos y servicios

Docker Engine/Compose v2, Node 22.12+ y npm para compilar el frontend; Python 3 para los servidores de prueba del frontend. cdk-dev incorpora Python 3.12, Node 22 y dependencias backend. No se necesita cuenta AWS, AWS CLI ni bootstrap CDK.

| Servicio | Función | Acceso |
| --- | --- | --- |
| ministack | API Gateway, Lambda, DynamoDB, S3 y CloudFormation locales | Host 127.0.0.1:4566 por defecto |
| redis | Presencia, caché y Tracking | Host 127.0.0.1:6379 por defecto |
| cdk-dev | Provisionar y ejecutar pytest; trabajo en /app | docker compose exec; sin socket Docker |
| osrm | Rutas de automóvil en extracto Santa Marta | Solo red Compose, osrm:5000; sin puerto host |
| web | Servidor estático/proxy de la aplicación | http://127.0.0.1:8080 |
| osm-download / osrm-prepare | Descargar/recortar/preparar MLD | Servicios puntuales del perfil geo-prepare |

Las versiones fijadas por defecto son MiniStack 1.5.36, Redis 7.4.2 y OSRM 5.27.1. Las imágenes pueden configurarse; el resultado con otra versión requiere validar de nuevo. La red es bridge, no `internal: true`. Los servicios pueden necesitar Internet para dependencias, extracto y tiles; los SDK de la aplicación apuntan al emulador local.

## Primera ejecución

Desde la raíz:

```bash
cp -n .env.example .env
docker compose --profile geo-prepare run --rm osm-download
docker compose --profile geo-prepare run --rm osrm-prepare
docker compose up -d --build --wait
docker compose exec -T cdk-dev python -m scripts.provision
# Opcional: usuarios de ejemplo habilitados.
docker compose exec -T cdk-dev python -m scripts.demo
npm --prefix frontend ci
npm --prefix frontend run build:local
```

`cp -n` conserva un .env existente. Ajustar DEV_UID/DEV_GID si difieren de 1000 para evitar archivos propiedad de root. .env, venv, outputs, ZIPs y extractos no se versionan. La preparación OSM requiere descarga y espacio local; los siguientes arranques reutilizan osrm-data. [Fuente, licencia, cobertura y preparación exacta](geo/README.md).

Abrir :8080. tienda_demo y rep_demo1/2/3 permiten probar pedidos; admin permite operar la bandeja. Para demostrar registro/aprobación, usar usuarios nuevos en sesiones independientes. Los códigos/secretos de ejemplo son de desarrollo y no acreditan identidad real.

## Actualizar una instalación existente

Después de incorporar cambios backend, repetir scripts.provision; cambiar archivos Python montados en cdk-dev no actualiza por sí solo el ZIP de las Lambdas desplegadas. Cambios de dependencias/imagen pueden exigir `docker compose up -d --build --wait`. Para cambios frontend, recompilar y recargar la página.

Perfiles creados antes de SPEC-10:

```bash
docker compose exec -T cdk-dev python -m scripts.backfill_approvals --dry-run
docker compose exec -T cdk-dev python -m scripts.backfill_approvals
docker compose exec -T cdk-dev python -m scripts.backfill_approvals --dry-run
```

El backfill añade metadatos/índices, conserva permisos/versiones y omite cambios concurrentes. Si concurrent es mayor que cero, repetir. No hay backfill de puntos de pedidos ni auditoría retroactiva. [Reglas de clasificación y uso](admin/README.md).

### Build normal, build local y Vite

- `npm --prefix frontend run build`: compilación normal sin controles de simulación.
- `npm --prefix frontend run build:local`: compilación con demo; backend también debe autorizar SIMULATED.
- Desde frontend, `npm run dev:preview`: Vite en :5173. La entrada principal es la aplicación; `/preview.html` mantiene el prototipo con fixtures. El proxy `/api/` apunta por defecto a :8080.

LocalStorage/sesión pertenece a cada origen. localhost y 127.0.0.1, o :5173 y :8080, no comparten automáticamente sesión. Usar el mismo origen dentro del recorrido de cada actor.

## Empaquetado e infraestructura

`scripts.provision` instala dependencias runtime fijadas con wheels Python 3.12/Linux x86_64, incorpora app/lambdas sin tests/.env y crea app/.local/artifacts/lambdas.zip. Las entradas tienen fechas/permisos estables; SHA-256 determina la clave del ZIP en S3 local. Mismo contenido produce la misma clave. El bucket local flashdelivery-local-assets se prepara fuera del stack como almacén de artefactos; no es un bootstrap AWS.

CDK sintetiza CloudFormation mediante su API Python y BootstraplessSynthesizer. El script publica el ZIP y aplica la plantilla con boto3. La clave lambdas/not-built.zip de una síntesis aislada es un marcador; desplegar con scripts.provision. El stack declara tabla/GSIs, roles, Lambdas y rutas. Health usa código inline; Readiness y módulos usan el paquete S3. La carpeta layers/dependencias conserva la estructura del curso, pero su contenido runtime se incluye en ZIP; no se declara una Layer no validada.

app/requirements.lock y app/layers/dependencias/requirements.lock fijan versiones directas/transitivas como restricciones. No incluyen hashes de wheels; imágenes fijadas por tags, no por digest. Los artefactos antiguos no se eliminan automáticamente.

## Outputs y sondas

app/.local/outputs.json contiene ApiId y URLs. Un output generado dentro de cdk-dev puede referenciar ministack:4566, válido en Compose pero no como DNS del navegador. Desde host, usar :8080 o `http://127.0.0.1:4566/_aws/execute-api/<ApiId>/local`.

| Ruta | Alcance |
| --- | --- |
| /health y /api/v1/health | Ejecutan la Lambda de salud, sin comprobar dependencias |
| /api/v1/ready | Lambda empaquetada: DescribeTable y PING; 503 ante fallo |

Readiness no acredita permisos IAM equivalentes a AWS, rutas OSRM ni una entrega completa. OSRM tiene healthcheck de ruta independiente. La API tiene 40 operaciones de módulos + 3 sondas; no contar cada Lambda como una sola ruta.

Los clientes usan endpoint explícito local y test/test. MiniStack sin AUTH puede inyectar access key ficticia 000000000000; Settings contempla ese caso. No introducir credenciales AWS reales. Las variables reservadas del runtime AWS se dejan al ejecutor local.

## Pruebas reproducibles

```bash
# Sin red: fixtures moto/fakeredis; integration queda excluido por pytest.ini.
docker compose exec -T cdk-dev python -m pytest tests/ -q
# Paquete/servicios reales locales; requiere provisionamiento y OSRM sano.
docker compose exec -T cdk-dev python -m pytest tests/integration/ -m integration -q
# Alternativa para seleccionar ambas clases explícitamente:
docker compose exec -T cdk-dev python -m pytest tests/ -m 'integration or not integration' -q
```

La selección explícita conserva integraciones en lugar de reemplazarlas por mocks. Los unitarios bloquean conexiones accidentales. Los escenarios reales crean IDs propios y limpian por clave, incluida auditoría; no vacían tabla ni Redis.

Desde frontend: npm ci, build, lint, npm test y test:design; instalar Chromium con `npx playwright install chromium`. Suites disponibles: test:e2e, test:design:e2e, test:unified:e2e, test:geo:e2e y test:geo:production. La de producción presupone build normal. Para test:geo:real, recompilar build:local y mantener :8080/backend/OSRM activos. GEO_PYTHON configura el Python host con boto3/python-dotenv para fixtures. No publica secretos ni trazas del recorrido real. [Comandos y cobertura GEO](geo/README.md), [resultados fechados](validation.md).

## Persistencia y limpieza

MiniStack, Redis AOF y OSRM usan volúmenes. `docker compose down` conserva volúmenes; añadir --volumes los elimina. No es un procedimiento necesario para resolver un conflicto de negocio o recargar una Lambda.

La prueba de reinicio se ejecuta desde el host con Docker accesible, fuera de otras suites:

```bash
cd app
../.venv/bin/python -m scripts.check_persistence
```

Escribe marcadores UUID, reinicia ordenadamente sin borrar volúmenes, verifica y limpia únicamente sus claves. Guarda app/.local/persistence.json. No prueba corte eléctrico, recuperación ante corrupción ni respaldo de producción. No se ejecuta reinicio dentro de pytest.

Los comandos seed/demo --clean borran exclusivamente su conjunto reservado. Un benchmark crea y limpia su namespace; puede consumir tiempo/recursos. No ejecutar borrados de volúmenes durante escenarios reales. Evidencia histórica de carga: informe-calidad.md.

## Diagnóstico frecuente

| Síntoma | Comprobación/acción |
| --- | --- |
| Front no muestra cambios | Recompilar build:local y recargar; comprobar que se está usando el origen correcto |
| Endpoint nuevo responde 404 | Revisar ApiId/outputs y volver a provisionar el ZIP y rutas |
| Bandeja no muestra perfiles antiguos | Backfill; verificar contadores; después Actualizar; el GSI es eventual |
| Aprobar/suspender devuelve 409 | Leer perfil/version actual; entrega activa exige resolverla antes; no borrar ACTIVE manualmente |
| Oferta aparece pero aceptar falla | Otro repartidor pudo ganar; el índice no garantiza disponibilidad actual |
| 503 de presencia | Verificar salud Redis; no interpretar la lista vacía como permiso para adjudicar |
| Mapa no tiene fondo | Revisar proveedor/atribución/política de tiles y red; estado textual puede seguir funcionando |
| Ruta no disponible | Verificar osrm-data preparado, healthcheck OSRM, cobertura y ambos puntos del pedido |
| Simulador deshabilitado | Build local, autorización backend local, puntos, inicio y consentimiento; leer motivo junto al botón |
| JSII rechaza caché del host | Preferir cdk-dev; alternativa conocida: JSII_RUNTIME_PACKAGE_CACHE=disabled en la invocación |
| Chromium no se encuentra | Instalar navegador; PLAYWRIGHT_BROWSERS_PATH debe coincidir si se eligió directorio alternativo |

No se solucionan fallos de caché cambiando el estado oficial ni errores de despliegue simulando respuestas exitosas. Un cambio de proveedor/motor requiere una nueva validación, no asumir equivalencia con otro emulador.
