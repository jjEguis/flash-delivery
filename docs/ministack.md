# Verificación de MiniStack

Actualización 2026-11-12: ejecución directa del incremento 0 completada. Persistencia tras reinicio ordenado y Lambda empaquetada desde S3, con DynamoDB/Redis accesibles desde el runtime, verificadas. Suite: **20 passed** antes y después del reinicio sin reprovisionar. La matriz siguiente conserva la evidencia de la fase anterior; los resultados actuales están en [validación](validation.md).

Fuentes oficiales consultadas el 10 de noviembre de 2026:

- [Proyecto y catálogo](https://github.com/ministackorg/ministack).
- [Versión del código](https://github.com/ministackorg/ministack/blob/main/pyproject.toml): 1.5.36.
- [Compose oficial](https://github.com/ministackorg/ministack/blob/main/docker-compose.yml).
- [Implementación DynamoDB](https://github.com/ministackorg/ministack/blob/main/ministack/services/dynamodb.py).
- [Implementación HTTP API](https://github.com/ministackorg/ministack/blob/main/ministack/services/apigateway.py).
- [Publicación de imágenes versionadas](https://github.com/ministackorg/ministack/blob/main/.github/workflows/docker-publish.yml).

| Capacidad | Evidencia en fuentes | Comprobación de este proyecto |
| --- | --- | --- |
| DynamoDB Put/Get/Update/Query | Catálogo e implementación | Test de escritura, lectura, actualización y Query por ambos GSIs; validado por el usuario con suite completa |
| GSI1/GSI2 | Soporte GSI en DynamoDB | DescribeTable, claves exactas y consultas; validado por el usuario |
| PAY_PER_REQUEST | Ejemplos oficiales CreateTable | BillingModeSummary; validado por el usuario |
| TransactWriteItems | Catálogo y handler DynamoDB | Commit y rollback condicional de dos operaciones; validado por el usuario |
| Python Lambda | Ejecutor local documentado | Handler verificado directamente; ejecución emulada validada por el usuario |
| HTTP API + AWS_PROXY | Implementación API Gateway v2 | GET por ruta de ejecución propia de MiniStack; validado por el usuario |
| CDK/CloudFormation | Proyecto declara compatibilidad | Plantilla sin assets ni bootstrap; síntesis comprobada aquí; aplicación confirmada por el usuario |
| Persistencia | PERSIST_STATE y STATE_DIR documentados | Volumen configurado; reinicio con conservación pendiente |

No se usaron variables de LocalStack ni se infirió compatibilidad a partir de él.
Se utiliza `/_ministack/health` y la ruta de
datos `/_aws/execute-api/...` que documenta
MiniStack. La configuración de persistencia y el ejecutor local siguen su documentación.
La versión del código no demuestra que su tag
 Docker pueda descargarse: debe comprobarse
con `docker compose pull` en el host de validación.

No se detectó una funcionalidad requerida explícitamente ausente en las fuentes.
No hay base para declarar una incompatibilidad concreta sin ejecutar el entorno.
Si la integración HTTP falla, la alternativa de biblioteca estándar permite verificar
el contrato del handler y deja pendiente API Gateway. Si fallan GSIs o atomicidad,
la fase permanece bloqueada: no sustituir MiniStack ni simular éxito automáticamente.
