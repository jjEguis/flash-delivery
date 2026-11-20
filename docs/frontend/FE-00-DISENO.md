# FE-00 — Decisiones de diseño

Referencia de requisitos: [SPEC-07 diseño v2.1](../specs/SPEC-07_FRONTEND_DESIGN_v2.1.md). Referencia visual: [HTML aportado](../FlashDelivery%20%E2%80%94%20Demo%20de%20interfaz.html). FE-00 y FE-01 están implementadas y su base visual fue aprobada; FE-02 y siguientes quedan pendientes.

## Dirección visual

Control logístico sin fricción: Manrope alojada localmente, verde/teal, superficies sobrias, jerarquía mediante espacio y tipografía. Se aplicó la skill `frontend-design` de `.agents/skills/frontend-design/SKILL.md`. La vista de comercio prioriza métricas y tabla; actividad acompaña. El repartidor prioriza disponibilidad y entrega activa, con acción principal visible y navegación inferior en móvil.

Tokens semánticos en `frontend/src/styles/themes.css`, escala y geometría en `tokens.css`, composición en `index.css`. Claro y oscuro tienen superficies, texto, estados y foco propios. El texto secundario claro se ajustó a `#586d67` y el verde principal a `#087d62` para cumplir contraste en sus superficies. Los estados incluyen texto e icono, además de color. Tras revisar capturas se aumentó la legibilidad de tablas y se compactó la tarjeta móvil para mantener la acción sobre la navegación inferior.

## Arquitectura del prototipo

React + TypeScript + Vite en `frontend/src/`, entrada independiente `preview.html`, salida `design-dist/`. `app/` contiene providers y shell, `components/` primitivas, `features/` vistas por actor, `mocks/` datos locales y `styles/` tokens y estilos. El HTML funcional y su proxy siguen disponibles en :8080.

El provider de tema resuelve Sistema/Claro/Oscuro, guarda `flashdelivery:theme:v1`, responde a cambios del sistema y funciona sin almacenamiento. Un script previo al render aplica el tema inicial. Los diálogos nativos gestionan foco y Escape; se respeta movimiento reducido. La fuente no requiere solicitudes a terceros.

| Actor | Rutas del prototipo | Prioridad |
| --- | --- | --- |
| Comercio | `/app/store`, `/app/store/orders` | Resumen, pedidos, creación simulada y detalle |
| Repartidor | `/app/courier`, `/app/courier/available`, `/app/courier/history` | Entrega activa, disponibilidad, ofertas e historial |
| Destinatario | `/track/demo` | Seguimiento sin sidebar, direcciones ni datos privados |
| Administración | `/app/admin` | Estructura secundaria con funciones futuras deshabilitadas |

Las rutas son fragmentos después de `preview.html#`. Los datos y acciones viven en memoria; recargar o restablecer reinicia la demostración. No hay autenticación real ni llamadas a API.

## Contrato y brechas para la integración

El contrato vigente es [OpenAPI JSON](../api/openapi.json). Crear un pedido admite `pickupAddress`, `dropoffAddress` y `feeMinor`; la zona corresponde al comercio. El formulario no introduce destinatario, teléfono ni notas. No se implementan edición de perfil, búsqueda global, listas administrativas globales ni métricas globales sin soporte contractual. Los controles futuros aparecen deshabilitados.

La próxima integración debe conservar el cliente HTTP, la idempotencia y la paginación actuales; no asumir que los fixtures representan una respuesta de API. Las métricas de esta demostración se derivan de sus fixtures. Antes de FE-02 se revisarán visualmente comercio, repartidor y ambos temas con el usuario; las siguientes etapas requieren su propio alcance y pruebas.
