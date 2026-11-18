# Documentación de FlashDelivery

Actualizada el 2026-11-18 contra SPEC-00 a SPEC-10 fusionadas en develop. SPEC-11 reconcilia la documentación y amplía la guía de estudio; no implementa nuevos endpoints.

## Para estudiar y sustentar

1. **[Documento general: arquitectura y guía de estudio](ARQUITECTURA_GENERAL.md).** Negocio, diagrama de componentes/estados, diferencia entre primary key/partition key/sort key, razones de cada clave, GSIs, pedido de ejemplo, transacciones, Redis, permisos y preguntas de repaso.
2. **[Modelo físico](data-model/README.md).** Los once tipos de ítem, atributos, PK/SK, índices, validación, versiones y migración. [Catálogo JSON sintético](data-model/catalogo-items.json).
3. **[Patrones de acceso AP01–AP16](data-access-patterns.md).** Pregunta → clave → repositorio/endpoint → consistencia y paginación.
4. **[Contratos y colaboración](module-contracts.md).** Funciones implementadas, DTOs, dependencias efectivas y frontera del commit; sin presentar protocolos propuestos como código existente.
5. **[Resumen técnico](architecture.md).** Vista rápida de componentes y garantías.

## Para ejecutar, probar y administrar

| Necesidad | Documento |
| --- | --- |
| Arranque, paquete, outputs, pruebas y diagnóstico | [Entorno local](ENTORNO_LOCAL.md) y [README raíz](../README.md) |
| Registro → aprobación → pedido → recorridos → entrega | [Demo guiada](demo/README.md) |
| Aprobar/suspender/reactivar, auditoría y backfill | [Guía administrativa](admin/README.md) |
| OSRM, GPS, simulación, puntos, cobertura, ETA y tiles | [Guía GEO](geo/README.md) |
| Endpoints y schemas exactos | [OpenAPI](api/openapi.json) |
| Evidencia fechada y límites de cada ejecución | [Validación](validation.md) |
| Compatibilidad del emulador | [MiniStack](ministack.md) |
| Medición histórica de carga local | [Informe de calidad SPEC-06](informe-calidad.md) |

## Estado, diseño e historia

- [Plan de trabajo](PLAN_DE_TRABAJO.md): lo fusionado, entrega actual y trabajo por priorizar.
- [Índice de SPECs](specs/README.md): requisitos de cada incremento, con su contexto temporal. Una especificación antigua no sustituye al contrato vigente cuando otro incremento la amplió.
- [Unificación visual](frontend/UNIFICACION.md), [FE-00](frontend/FE-00-DISENO.md), [FE-01](frontend/FE-01-REVISION.md): evolución desde el prototipo hasta la aplicación conectada. `preview.html` conserva fixtures.
- [GEO v1](geo/GEO-00.md) y [GPS v1](specs/SPEC-08_GPS_TRACKING.md) son antecedentes. [Seguimiento vial v2](specs/SPEC-08_LIVE_DELIVERY_TRACKING_v2.md) amplía el diseño con MapLibre, OSRM y puntos estáticos en DynamoDB. Las afirmaciones antiguas de «Leaflet» o «ninguna coordenada en DynamoDB» no describen la implementación actual.

Los documentos architecture.md, module-contracts.md y data-access-patterns.md se actualizaron a la implementación vigente; sus propuestas antiguas siguen en el historial Git. Las evidencias históricas conservan sus fechas y conteos: no se reescriben como si fueran ejecuciones nuevas.

Si hay una diferencia, contrastar primero código/registro de rutas, OpenAPI y pruebas; después corregir el documento afectado. El general explica motivos, el modelo fija almacenamiento y OpenAPI fija HTTP. No copiar una API propuesta a la interfaz sin implementarla y validarla.
