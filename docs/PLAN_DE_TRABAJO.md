# Plan de trabajo — FlashDelivery

Actualizado: 2026-11-18. Este documento describe el estado actual; los diagnósticos iniciales se conservan en el historial Git. Las evidencias de cada entrega están en [validación](validation.md).

## Base implementada y fusionada

SPEC-00 a SPEC-08 v2: entorno MiniStack/Redis y OSRM local, modelo de tabla única y consultas sin Scan, transacciones/idempotencia, identidad local, perfiles y habilitación, creación/asignación/ciclo de entrega, presencia y estadísticas, frontend funcional con temas y paginación, seguimiento público y rutas por fase con ETA aproximada. Contrato vigente: [OpenAPI](api/openapi.json).

El PR de SPEC-08 v2 fue fusionado en develop. No se necesita volver a implementar Orders, Dispatch, registro, habilitación por ID ni conexión del diseño a la API. El prototipo visual permanece separado como referencia.

## Incremento actual — SPEC-09: demo guiada

[Especificación](specs/SPEC-09-DEMO-GUIADA.md). Hace visibles los pasos de registro/aprobación, separa las sesiones de cada actor y guía la selección de puntos. Corrige el descarte silencioso de coordenadas incompletas y la reutilización de una ruta del simulador al pasar a PICKED_UP. Mantiene la autorización de estados y añade una prueba real desde el registro hasta la entrega, con aprobación por administrador desde la UI.

No se fusionará el PR de este incremento sin autorización. El resultado de pruebas, capturas y limitaciones se registrará en docs/validation.md.

## Próximo incremento propuesto — aprobaciones administrativas

Antes de implementar, concretar una nueva SPEC con:

- Consulta paginada de comercios/repartidores pendientes y habilitados, limitada a ADMIN.
- Patrón de acceso DynamoDB e índices/proyecciones necesarios, sin introducir Scan como consulta operativa.
- Aprobación, suspensión/reactivación y tratamiento de un repartidor con pedido activo.
- Si se exige auditoría: actor administrador, fecha, motivo, retención y patrón de consulta.
- Estados vacíos/errores, confirmaciones y pruebas de permisos e integración real.

La habilitación por identificador ya funciona; falta el listado y su contrato. No inventar ese endpoint desde el frontend ni aprobar perfiles automáticamente como atajo de demo.

## Trabajo posterior por priorizar

1. Reconciliar los criterios de FE-02 a FE-06 con las vistas ya integradas: identificar brechas reales como búsqueda, ordenación y edición de perfil, evitando rehacer pantallas existentes.
2. Revisar las alertas de dependencias y la carga inicial del motor cartográfico en una SPEC de mantenimiento.
3. Validar GPS en teléfono y accesibilidad con lector de pantalla humano; registrar resultados observados.
4. Reconciliar notas históricas restantes de arquitectura/compatibilidad con OpenAPI y validación actuales.

## Decisiones de alcance

La entrega actual es una demostración académica local, con autenticación de desarrollo y MiniStack; no se ha autorizado migración a AWS real. Antes de convertirla en producto se deben especificar identidad/recuperación de cuenta, despliegue y operación, respaldo/retención y proveedor cartográfico según uso. Pagos, notificaciones, geocodificación, precios automáticos, seguimiento en segundo plano y optimización multientrega requieren alcance adicional aprobado.
