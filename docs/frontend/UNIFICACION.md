# Unificación del diseño funcional

> Estado al 2026-11-18: esta integración está fusionada. SPEC-09 añadió la demo guiada y SPEC-10 las bandejas administrativas auditadas; los párrafos siguientes documentan las decisiones de la unificación original. [Guía de estudio vigente](../ARQUITECTURA_GENERAL.md), [administración](../admin/README.md).

Solicitud del usuario: aplicar el diseño aprobado a toda la aplicación antes de continuar ajustes de GPS. Se actualiza el PR de SPEC-08 abierto, sin modificar contratos del backend.

Dirección visual (skill frontend-design): Manrope local, texto #132c2b y superficie #ffffff sobre #f6f8f8; acción verde #087d62; oscuro #0b1417 y superficies #142226. Se reutilizan los tokens, botones, estados y navegación de FE-01, evitando una segunda paleta. Comercio prioriza la tabla y métricas de alcance explícito; repartidor prioriza disponibilidad y pedido activo. El acceso y seguimiento público mantienen una cabecera compacta y no muestran navegación privada.

```text
Escritorio autenticado           Móvil autenticado
[sidebar][cabecera + tema]       [menú][título][tema]
         [título / acción]      [tarea prioritaria]
         [métricas reales]      [contenido]
         [tabla][formulario]    [navegación inferior]
```

Las métricas usan el contrato actual: mes consultado, filas cargadas y presencia visible; no se inventan totales globales. Se conserva el cliente HTTP, la idempotencia, cursores, heartbeat, registro, habilitación y transiciones. La copia de interfaz se centra en entregas y acciones; se retiran detalles de infraestructura de las pantallas.

La aplicación funcional se compila con Vite y se sirve en :8080. Un shell React compartido en apariencia rodea las vistas funcionales, que conservan sus casos de uso. Los mapas se montan dentro de ese shell; los enlaces anteriores redirigen a la ruta integrada. El prototipo FE-01 queda como referencia visual explícita en `preview.html`.

## Cobertura y evidencias

Vistas cubiertas: acceso, registro y habilitación pendiente, panel y pedidos de comercio, disponibilidad/pedido activo/ofertas/historial del repartidor, administración, seguimiento público y mapas internos/públicos. Los enlaces de navegación por sección conservan el estado y cursores cargados. La vista pública oculta barra lateral e identidad privada, aun con una sesión iniciada.

La aplicación se sirve en http://127.0.0.1:8080 después de `npm ci` y `npm run build:local` en `frontend/`. `npm run build` excluye el simulador. El servidor responde con una instrucción de compilación si falta la entrada construida; ya no sirve una interfaz antigua como alternativa.

Capturas de las vistas funcionales con fixtures controlados de navegador (no acreditan API real): [acceso](../evidencias/frontend-unificado/access-light-1440.png), [comercio claro](../evidencias/frontend-unificado/store-light-1440.png), [comercio oscuro](../evidencias/frontend-unificado/store-dark-1440.png), [repartidor móvil](../evidencias/frontend-unificado/courier-dark-390.png), [administración](../evidencias/frontend-unificado/admin-light-1440.png), [seguimiento público móvil](../evidencias/frontend-unificado/tracking-dark-390.png). Las [capturas de mapa](../geo/README.md) se obtienen con el smoke de API real.

Se inspeccionaron capturas de comercio y repartidor. Se corrigió el ancho mínimo de la tabla para mantener el desplazamiento dentro de su región en móvil; los formularios mantienen sus controles accesibles. El pedido activo precede a las ofertas tanto en el DOM como en la presentación visual. Las respuestas tardías de una vista anterior no pueden reemplazar la pantalla actual ni reiniciar sus intervalos después de navegar.

Comprobaciones reproducibles: `npm run lint`, `npm run build`, `npm run test:design`, `npm test`, `npm run test:e2e`, `npm run test:design:e2e`, `npm run test:geo:e2e`, `npm run test:geo:production`, `npm run test:unified:e2e`. Para el smoke real: `npm run build:local` y `npm run test:geo:real` con el stack provisionado. Resultados en [validación](../validation.md).
