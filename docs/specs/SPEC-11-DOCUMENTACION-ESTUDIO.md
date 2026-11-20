# SPEC-11 — Documentación vigente y guía de estudio

Fecha: 2026-11-18. Base: develop `5f85467`, después del merge de SPEC-10/PR #15. Estado: implementada, validada y fusionada mediante PR #16.

## Objetivo y alcance

Por solicitud del usuario, actualizar y completar la documentación del proyecto y el documento general para estudiar la arquitectura. Explicar single table design a partir de las preguntas de negocio y justificar partition key, sort key, primary key, prefijos, índices y vistas. Este incremento no modifica handlers, servicios, UI, infraestructura ejecutable, contratos HTTP ni datos del entorno.

## Entregables

- Documento general 2.0 con ruta de lectura, glosario, diagramas, motivos de cada clave, GSI1/GSI2, un pedido completo, carreras, idempotencia, Redis, geografía, permisos, operación y preguntas de repaso.
- Modelo físico de once tipos y catálogo sintético completo; matriz AP01–AP16 con fuente/repositorio/endpoint, consistencia y paginación.
- architecture.md, module-contracts.md y data-access-patterns.md actualizados al código; sus propuestas anteriores permanecen en Git.
- Índice documental, README, plan, estados de SPECs, entorno y compatibilidad reconciliados. Mantener evidencias antiguas como históricas, sin presentarlas como pruebas nuevas.
- Fuentes oficiales para conceptos DynamoDB y enlaces al código que implementa las decisiones del proyecto.

## Criterios de aceptación

1. La guía diferencia `(PK, SK)` de PK, clave lógica de partición física, vista de aplicación de proyección GSI, y datos oficiales de datos efímeros.
2. Las claves/índices explicados coinciden con model.layout y keys.py; ningún tipo de REQUIRED falta en el catálogo y todos los ejemplos pasan model.validate.
3. La matriz preserva AP01–AP14 y documenta AP15/AP16 como accesos técnicos existentes; no inventa nuevos endpoints. Las 40 operaciones del registro coinciden con OpenAPI y handlers.
4. Se explican Put con CAS, ACTIVE, idempotencia, auditoría y carrera suspensión/accept sin atribuir atomicidad a Redis ni exigir tabla única como requisito de transacciones DynamoDB.
5. Se reflejan MapLibre/OSRM, puntos estáticos E6, ubicación efímera, credencial de seguimiento, permisos geográficos y autenticación local; no se mantienen afirmaciones antiguas como actuales.
6. Comprobar enlaces locales de Markdown y referencias al código, ejemplos, contrato/modelo y whitespace. No desplegar ni ejecutar migraciones para un cambio documental.
7. Actualizar docs/validation.md con las comprobaciones efectivamente ejecutadas; commit, rama y PR a develop, sin fusionarlo.
