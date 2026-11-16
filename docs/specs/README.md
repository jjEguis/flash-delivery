# Especificaciones de FlashDelivery

Base importada del paquete v1.1 aportado por el usuario. Son requisitos y criterios de aceptación; su presencia no implica implementación ni validación. Consultar el [plan](../PLAN_DE_TRABAJO.md) para conocer las brechas actuales.

Estado: SPEC-00 a SPEC-08 implementadas, con evidencias en [validación](../validation.md). Resultados de calidad en el [informe](../informe-calidad.md).

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
| 8 | [Ubicación y seguimiento](SPEC-08_GPS_TRACKING.md) | Redis efímero, simulador, GPS optativo y mapas con permisos; [guía](../geo/README.md) |

El contrato vigente está en [OpenAPI](../api/openapi.json). Para nuevas funcionalidades, detallar actor, entradas, autorización, precondiciones, resultados, errores, persistencia y pruebas. `requestId` de trazabilidad e `Idempotency-Key` son conceptos distintos; mantener esa separación en API y frontend.

## Diseño frontend v2.1

[SPEC-07 de diseño v2.1](SPEC-07_FRONTEND_DESIGN_v2.1.md) es un trabajo adicional a la SPEC-07 de fiabilidad. FE-00/FE-01 implementadas como prototipo aislado, base visual aprobada y PR fusionado; FE-02 y siguientes pendientes. Consultar [decisiones](../frontend/FE-00-DISENO.md), [guía y capturas](../frontend/FE-01-REVISION.md). No está conectado a la API.

La aplicación funcional adopta el [diseño unificado](../frontend/UNIFICACION.md) en :8080, incluidos mapas dentro de la navegación. El prototipo de diseño mantiene sus fixtures únicamente como referencia.
