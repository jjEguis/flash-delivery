# Registro de validación

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
