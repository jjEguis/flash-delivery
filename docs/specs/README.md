# Especificaciones de FlashDelivery

Base importada del paquete v1.1 aportado por el usuario. Son requisitos y criterios de aceptación; su presencia no implica implementación ni validación. Consultar el [plan](../PLAN_DE_TRABAJO.md) para conocer las brechas actuales.

Estado: SPEC-00 a SPEC-07 implementadas, con evidencias en [validación](../validation.md). Resultados de calidad en el [informe](../informe-calidad.md).

| Orden | Especificación | Resultado esperado |
| --- | --- | --- |
| 0 | [Infraestructura](SPEC-00-INFRA-MINISTACK.md) | Entorno y despliegue local verificables |
| 1 | [Datos](SPEC-01-DYNAMODB.md) | Claves, índices y consultas por patrón de acceso |
| 2 | [Transacciones](SPEC-02-TRANSACCIONES.md) | Estados, unicidad e idempotencia |
| 3 | [Contratos](SPEC-03-CONTRATOS.md) | API, identidad y permisos |
| 4 | [Primer flujo](SPEC-04-IMPLEMENTACION-BASE.md) | Comercio habilitado crea y consulta pedidos |
| 5 | [Asignación y lecturas](SPEC-05-DISPATCH-Y-LECTURAS.md) | Aceptar, recoger, entregar, cancelar, presencia, seguimiento y métricas |
| 6 | [Calidad](SPEC-06-CALIDAD.md) | Evidencia reproducible de corrección y rendimiento |
| 7 | [Fiabilidad del frontend](SPEC-07-FRONTEND-FIABILIDAD.md) | Reintentos persistidos, paginación del repartidor y tests de navegador |

El contrato vigente está en [OpenAPI](../api/openapi.json). Para nuevas funcionalidades, detallar actor, entradas, autorización, precondiciones, resultados, errores, persistencia y pruebas. `requestId` de trazabilidad e `Idempotency-Key` son conceptos distintos; mantener esa separación en API y frontend.
