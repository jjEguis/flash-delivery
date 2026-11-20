# Arquitectura ejecutable — resumen técnico

Revisión: 2026-11-18, SPEC-00 a SPEC-10. La propuesta inicial fue sustituida por este resumen; su historial permanece en Git. Para estudiar las decisiones con ejemplos, leer [Arquitectura y guía de estudio](ARQUITECTURA_GENERAL.md).

## Componentes

SPA funcional híbrida: controladores JavaScript y shell/componentes React/TypeScript, compilados con Vite. `frontend/server.py` sirve design-dist y hace proxy de `/api/` a API Gateway en MiniStack. `preview.html` es referencia con fixtures, no la aplicación conectada. Los mapas viven dentro de la navegación y usan MapLibre.

API Gateway enruta a una Lambda Python 3.12 por módulo: Identity, Stores, Couriers, Orders, Dispatch, Availability, Tracking, Analytics y Approvals. Se suman Health/Readiness. Handlers `main(event, context)`; servicios Python coordinan reglas; repositorios producen lecturas/acciones DynamoDB. No hay llamadas Lambda-a-Lambda.

Tabla única FlashDeliveryTable con PK/SK y GSI1/GSI2 dispersos, proyección ALL. Sus once tipos separan entidades oficiales, vistas de lectura, eventos, ACTIVE, idempotencia, credencial pública y auditoría de perfil. El índice lo replica el motor; las vistas las escribe el código en transacciones. [Modelo](data-model/README.md), [patrones](data-access-patterns.md), [contratos](module-contracts.md).

Redis conserva presencia, caché mensual, última posición y snapshots/locks de rutas. OSRM 5.27.1 calcula rutas locales desde Lambda; no publica puerto al host. Los tiles son externos y los carga el navegador. Solo los puntos estáticos opcionales de recogida/entrega se guardan en DynamoDB; no hay historial GPS persistente.

## Garantías y límites

- Un repartidor por pedido: transición condicionada a la versión de META.
- Una entrega activa por repartidor: creación exclusiva de COURIER#id / ACTIVE.
- Consistencia de estado/eventos/vistas/agregado/intención: commit DynamoDB común según operación.
- Suspensión segura: perfil y auditoría atómicos; ausencia de ACTIVE dentro del commit al suspender repartidor.
- GetItem/Query base fuertes; GSIs eventuales. Leer no bloquea; la condición del commit resuelve carreras.
- Redis no adjudica ni revierte pedidos. No hay transacción distribuida con Redis/OSRM.
- Autenticación local HMAC; IAM sintetizado con permisos amplios a tabla para módulos, sin acreditar aplicación productiva en MiniStack.

## Despliegue y evidencia

CDK genera CloudFormation; scripts.provision crea un ZIP de runtime reproducible, publica S3 local y aplica la plantilla mediante boto3. BootstraplessSynthesizer evita un bootstrap AWS. Solo Health usa código inline; los módulos/Readiness usan el paquete. Los outputs se escriben en app/.local, fuera de Git.

Compose incorpora MiniStack 1.5.36, Redis 7.4.2, cdk-dev, OSRM y web; dos servicios de preparación se activan por perfil. Red bridge local; puertos web/MiniStack/Redis en loopback. Volúmenes preservan datos en reinicio ordenado. [Entorno](ENTORNO_LOCAL.md), [compatibilidad](ministack.md).

La cobertura combina unitarios sin red, integración local, carreras concurrentes y navegador con API real. Los resultados fechados y sus límites se conservan en [validación](validation.md). No hay despliegue AWS real, verificación de GPS físico ni promesa de rendimiento productivo.
