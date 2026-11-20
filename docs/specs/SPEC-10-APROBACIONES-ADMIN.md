# SPEC-10 — Bandeja de aprobación y auditoría administrativa

Estado: implementada, validada y fusionada mediante PR #15. Base: develop con SPEC-09 fusionada.

## Alcance y decisiones

- ADMIN consulta comercios y repartidores por PENDING, ENABLED o SUSPENDED, con cursores. Las altas siguen pendientes hasta aprobación explícita.
- Se reutiliza GSI2 del perfil: `ADMIN#STORE|COURIER#estado / CREATED#fecha#id`. No hay nuevas tablas/GSIs ni Scan en endpoints. Los listados revalidan el perfil mediante lectura fuerte porque GSI2 es eventual; una página puede ser vacía con nextCursor.
- `approvalStatus` amplía perfiles sin cambiar su PK/SK. `enabled` sigue siendo el permiso efectivo. PENDING/SUSPENDED implican enabled=false. Disponibilidad y permisos existentes se conservan.
- Los PATCH existentes aceptan `expectedVersion` y `reason` opcionales. La UI envía ambos; clientes previos siguen enviando enabled. Una transición real actualiza perfil y crea evento de auditoría en la misma transacción. No-op repetido no incrementa versión ni duplica eventos. Una versión antigua que intenta otro cambio devuelve 409.
- Deshabilitar un repartidor con ACTIVE devuelve 409 COURIER_HAS_ACTIVE_ORDER, sin mutar nada. La ausencia de ACTIVE se comprueba en la transacción junto al perfil; competir con aceptación no puede producir un perfil suspendido y una nueva asignación. El administrador debe resolver/finalizar la entrega antes de suspender.
- Auditoría por perfil: actor administrador, fecha UTC, estado anterior/nuevo, versión y motivo. Retención indefinida en la demo hasta especificar otra política; no se inventa auditoría retroactiva ni se incluyen coordenadas/tokens.

## Contratos

Solo ADMIN; 401 sin sesión, 403 para otros roles, 404 para perfil inexistente, 400 para filtro/cursor/cuerpo inválidos, 409 por versión/entrega activa. Todos bajo /api/v1:

- GET /admin/stores?status=PENDING&limit=25&cursor=...
- GET /admin/couriers?status=PENDING&limit=25&cursor=...
- GET /admin/stores/{storeId}, GET /admin/couriers/{courierId}: detalle mínimo, con activeOrderId solo para repartidor.
- GET /admin/stores/{storeId}/events, GET /admin/couriers/{courierId}/events: auditoría paginada.
- PATCH previos: enabled booleano; expectedVersion entero positivo y reason 1–300 caracteres opcionales. UI exige motivo y confirma el cambio en un diálogo nativo.

## Migración

Script explícito de mantenimiento, paginado e idempotente, para añadir campos/índices a perfiles antiguos; Scan permitido únicamente en este script. Escritura condicional por versión y enabled para no sobreescribir cambios concurrentes. No cambia permisos ni versión de negocio, no crea aprobaciones/eventos ficticios. Estado legado inferido: enabled=true → ENABLED; false y versión 1 → PENDING; false con versión posterior → SUSPENDED (clasificación documentada, no prueba de una aprobación histórica). Los perfiles ya indexados no se reescriben. Un legado suspendido con ACTIVE debe reactivarse manualmente para resolver la entrega; la migración no lo modifica automáticamente.

## Interfaz

Mantener búsqueda manual por ID como alternativa. Bandejas separadas por tipo, con filtro de estado, filas de perfil, cargar más, actualizar, detalle y auditoría. Cambios con motivo, versión y confirmación; informar conflicto y actualizar datos sin mostrar éxito ficticio. Suspensión explica la regla de ACTIVE. Estado suspendido de la propia cuenta se distingue del registro pendiente.

Diseño: frontend-design; Manrope y tokens existentes. Paleta clara #ffffff/#f6f8f8/#132c2b, acción #087d62, aviso #9b5d12 y suspensión #aa3947; oscuro existente. Tarjetas de perfiles legibles en móvil, alineación izquierda, controles de 44–48 px. El detalle/confirmación usa dialog.showModal(), foco y Escape nativos. Se conserva el panel secundario de pedidos/presencia. No añadir métricas inventadas ni acceso GPS al administrador.

## Aceptación y evidencia

- Moto/fakeredis compartidos: permisos, estado/filtros/cursor, no Scan, reintentos/no-op, auditoría atómica y concurrencia suspensión/aceptación.
- Migración verificable sin pérdida de atributos/permisos ni sobrescritura por carreras.
- Integración MiniStack/Redis real, conservar pruebas previas.
- E2E de pendientes → detalle → aprobar → habilitados → suspender/reactivar → auditoría, ambos temas y móvil; 409/errores y sesiones independientes con API real.
- Actualizar OpenAPI, modelo de datos, guía, estado y docs/validation.md; commit, rama y PR hacia develop. No fusionar sin autorización.
