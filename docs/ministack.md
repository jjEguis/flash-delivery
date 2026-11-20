# Compatibilidad local de MiniStack

Revisión documental: 2026-11-18. Versión fijada por defecto en Compose: **ministackorg/ministack:1.5.36**. Redis y OSRM son servicios separados, no características emuladas de MiniStack. La evidencia de cada ejecución, incluida la más reciente de SPEC-10, está en [validación](validation.md).

## Qué está comprobado en el proyecto

| Capacidad | Evidencia local conservada | Límite de la afirmación |
| --- | --- | --- |
| DynamoDB y tabla/GSIs | Put/Get/Update/Query, índices dispersos y layout en tests de modelo/acceso | No acredita rendimiento ni coste AWS |
| TransactWriteItems | Commit/rollback, estados/vistas/idempotencia, 100 aceptaciones y carrera suspensión/accept | El comportamiento temporal del emulador puede diferir |
| API Gateway → Lambda Python | Módulos empaquetados y flujos HTTP integrados | No equivale al aislamiento runtime de AWS |
| S3/CloudFormation/CDK | Artefacto local reproducible, síntesis y aplicación mediante provision | No se usa bootstrap AWS ni se declara soporte universal de CDK |
| Acceso Redis desde Lambda | Presencia, caché y Tracking mediante red Compose | Redis no adjudica ni participa en transacción DynamoDB |
| Acceso OSRM desde Lambda | Geometría/progreso y recálculo en integración local | OSRM es privado al entorno Compose, no servicio AWS |
| Persistencia tras reinicio ordenado | Marcadores DynamoDB/Redis y servicios después de reinicio, registrado en la fase de infraestructura | No prueba corte eléctrico, backups ni desastre |
| IAM | Roles/permisos sintetizados | No se acredita enforcement equivalente a AWS |

Se usan rutas propias del emulador `/_ministack/health` y `/_aws/execute-api/<ApiId>/local`. No se utilizan variables de LocalStack ni se infiere compatibilidad a partir de él. Los SDK configuran endpoint local explícito.

MiniStack ejecuta Lambda Python localmente; el contenedor no necesita socket Docker. Los módulos comparten el paquete del proyecto y cada entrada usa `lambdas.<modulo>.handler.main`. Readiness comprueba dependencias, mientras las integraciones verifican operaciones y no solo un HTTP 200 de salud.

## Qué no se debe concluir

Las pruebas locales no demuestran latencia/distribución física/capacidad de DynamoDB real, propagación idéntica de GSI, facturación AWS ni aislamiento IAM productivo. La medición de 10k pedidos es evidencia histórica del emulador, con metodología y límites en [informe de calidad](informe-calidad.md).

El repositorio fija versiones observadas; no afirma que 1.5.36 sea la versión más reciente del proveedor. Actualizar imagen o cambiar de emulador requiere repetir las integraciones. Las pruebas de persistencia se ejecutan separadas de otras suites para no interrumpirlas.

## Reproducción y procedencia

Usar los comandos de [entorno local](ENTORNO_LOCAL.md) para provisionar y ejecutar pytest con `-m integration`. Si faltan GSIs/atomicidad/rutas, registrar el fallo y corregirlo: una prueba directa del handler no sustituye a API Gateway y un mock no acredita integración.

Proyecto de referencia del emulador: [ministackorg/ministack](https://github.com/ministackorg/ministack). La evidencia de compatibilidad que se presenta aquí procede del código/configuración y tests de FlashDelivery sobre la imagen fijada, no de interpretar su catálogo como garantía de paridad AWS.
