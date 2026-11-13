# Especificaciones de FlashDelivery

Base importada del paquete v1.1 aportado por el usuario. Son requisitos y criterios de aceptación; su presencia no implica implementación ni validación. Consultar el [plan](../PLAN_DE_TRABAJO.md) para conocer las brechas actuales.

| Orden | Especificación | Resultado esperado |
| --- | --- | --- |
| 0 | [Infraestructura](SPEC-00-INFRA-MINISTACK.md) | Entorno y despliegue local verificables |
| 1 | [Datos](SPEC-01-DYNAMODB.md) | Claves, índices y consultas por patrón de acceso |
| 2 | [Transacciones](SPEC-02-TRANSACCIONES.md) | Estados, unicidad e idempotencia |
| 3 | [Contratos](SPEC-03-CONTRATOS.md) | API, identidad y permisos |
| 4 | [Primer flujo](SPEC-04-IMPLEMENTACION-BASE.md) | Comercio habilitado crea y consulta pedidos |
| 5 | [Asignación y lecturas](SPEC-05-DISPATCH-Y-LECTURAS.md) | Aceptar, recoger, entregar, cancelar, presencia, seguimiento y métricas |
| 6 | [Calidad](SPEC-06-CALIDAD.md) | Evidencia reproducible de corrección y rendimiento |

Antes de implementar, completar en cada funcionalidad: actor, entradas, autorización, precondiciones, resultado, errores, persistencia y pruebas. SPEC-03 debe cerrar también habilitación administrativa de perfiles, consulta de pedido activo y entrega del token de seguimiento; no basta con las rutas resumidas actuales.

El OpenAPI del paquete original sigue siendo borrador v1.0. Debe alinearse con estas especificaciones antes de usarse para generar código. `requestId` de trazabilidad e `Idempotency-Key` son conceptos distintos: fijar explícitamente su traducción al contrato de aplicación.
