# Plan de trabajo — FlashDelivery

Actualizado: 2026-11-18. Este documento describe el estado actual; los diagnósticos iniciales se conservan en el historial Git. Las evidencias de cada entrega están en [validación](validation.md).

## Base implementada y fusionada

SPEC-00 a SPEC-10: entorno MiniStack/Redis y OSRM local, modelo de tabla única y consultas sin Scan, transacciones/idempotencia, identidad local, perfiles y habilitación, creación/asignación/ciclo de entrega, presencia y estadísticas, frontend funcional con temas y paginación, bandejas administrativas con auditoría/suspensión segura, seguimiento público y rutas por fase con ETA aproximada. Contrato vigente: [OpenAPI](api/openapi.json).

SPEC-10 se fusionó mediante [PR #15](https://github.com/jjEguis/flash-delivery/pull/15), base develop `5f85467`. No hay que rehacer registro, listados administrativos, asignación ni integración visual para avanzar. Los perfiles antiguos requieren la migración explícita descrita en la [guía administrativa](admin/README.md).

## Incremento actual — SPEC-11: documentación y estudio

[Especificación](specs/SPEC-11-DOCUMENTACION-ESTUDIO.md). Reconciliar el documento general y las guías técnicas con el código fusionado: single table, motivación de cada PK/SK, GSIs, AP01–AP16, transacciones, idempotencia, Redis, geografía, permisos y operación. Añadir ejemplos verificables y preguntas para sustentación; distinguir propuestas históricas de funciones implementadas. Sin cambios de código de negocio ni despliegue.

Entregar en rama/PR propio hacia develop, sin fusionar automáticamente. La [guía general](ARQUITECTURA_GENERAL.md) es la lectura principal; [índice documental](README.md) organiza el resto.

## Trabajo posterior por priorizar

1. Reconciliar los criterios de FE-02 a FE-06 con las vistas ya integradas: identificar brechas reales como búsqueda, ordenación y edición de perfil, evitando rehacer pantallas existentes.
2. Revisar las alertas de dependencias y la carga inicial del motor cartográfico en una SPEC de mantenimiento.
3. Validar GPS en teléfono y accesibilidad con lector de pantalla humano; registrar resultados observados.
4. Antes de ampliar funcionalidad, especificar sus nuevas preguntas de acceso y revisar costes/consistencia; mantener código, OpenAPI y documentación alineados.

## Decisiones de alcance

La entrega actual es una demostración académica local, con autenticación de desarrollo y MiniStack; no se ha autorizado migración a AWS real. Antes de convertirla en producto se deben especificar identidad/recuperación de cuenta, despliegue y operación, respaldo/retención y proveedor cartográfico según uso. Pagos, notificaciones, geocodificación, precios automáticos, seguimiento en segundo plano y optimización multientrega requieren alcance adicional aprobado.
