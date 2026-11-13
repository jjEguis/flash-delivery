# Registro de validación

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
