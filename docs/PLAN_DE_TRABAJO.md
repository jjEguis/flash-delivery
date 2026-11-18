# Plan de trabajo — FlashDelivery

Actualizado: 2026-11-18. Este documento describe el estado actual; los diagnósticos iniciales se conservan en el historial Git. Las evidencias de cada entrega están en [validación](validation.md).

## Base implementada y fusionada

SPEC-00 a SPEC-09: entorno MiniStack/Redis y OSRM local, modelo de tabla única y consultas sin Scan, transacciones/idempotencia, identidad local, perfiles y habilitación, creación/asignación/ciclo de entrega, presencia y estadísticas, frontend funcional con temas y paginación, seguimiento público y rutas por fase con ETA aproximada. Contrato vigente: [OpenAPI](api/openapi.json).

El PR de SPEC-08 v2 fue fusionado en develop. No se necesita volver a implementar Orders, Dispatch, registro, habilitación por ID ni conexión del diseño a la API. El prototipo visual permanece separado como referencia.

## Incremento actual — SPEC-10: aprobaciones administrativas

[Especificación](specs/SPEC-10-APROBACIONES-ADMIN.md). Bandejas paginadas por estado para comercios y repartidores, detalle y auditoría. Aprobación/suspensión/reactivación con motivo y versión, confirmación nativa y guard transaccional contra suspensión con entrega activa. Reutiliza GSI2 y requiere migración explícita para perfiles antiguos. [Guía](admin/README.md).

SPEC-09 ya fue fusionada en develop. SPEC-10 se entrega en su propia rama y PR; pendiente revisión. No fusionar sin autorización. Evidencia en docs/validation.md.

## Trabajo posterior por priorizar

1. Reconciliar los criterios de FE-02 a FE-06 con las vistas ya integradas: identificar brechas reales como búsqueda, ordenación y edición de perfil, evitando rehacer pantallas existentes.
2. Revisar las alertas de dependencias y la carga inicial del motor cartográfico en una SPEC de mantenimiento.
3. Validar GPS en teléfono y accesibilidad con lector de pantalla humano; registrar resultados observados.
4. Reconciliar notas históricas restantes de arquitectura/compatibilidad con OpenAPI y validación actuales.

## Decisiones de alcance

La entrega actual es una demostración académica local, con autenticación de desarrollo y MiniStack; no se ha autorizado migración a AWS real. Antes de convertirla en producto se deben especificar identidad/recuperación de cuenta, despliegue y operación, respaldo/retención y proveedor cartográfico según uso. Pagos, notificaciones, geocodificación, precios automáticos, seguimiento en segundo plano y optimización multientrega requieren alcance adicional aprobado.
