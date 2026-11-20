# FE-01 — Revisión del prototipo

Estado: base visual aprobada por el usuario y PR #11 fusionado. No implica completar toda la SPEC de diseño v2.1.

Desde `frontend/`, con Node 22.12 o superior:

```bash
npm ci
npm run dev:preview
```

Abrir http://127.0.0.1:5173/preview.html. No necesita Docker ni API. Para comprobar compilación: `npm run build`; genera `design-dist/`. `npm run preview` sirve esa compilación en el mismo puerto, después de detener el servidor de desarrollo.

## Flujo para revisar

1. En Comercio, alternar Sistema/Claro/Oscuro, revisar métricas y abrir un pedido.
2. Usar «Nueva entrega», probar validación y confirmar. El pedido y las métricas cambian solo en la demo.
3. Cambiar «Vista» a Repartidor; recoger y entregar el pedido activo. Revisar disponibles e historial y alternar disponibilidad.
4. En «Estado», probar carga, vacío, error y conflicto. Restablecer permite volver a los fixtures iniciales.
5. Revisar Seguimiento y Administración desde el selector de vista. Seguimiento no muestra datos privados; los controles futuros de administración están deshabilitados.
6. Repetir en móvil: menú, navegación inferior, formularios y acción principal. La aplicación funcional sigue en http://127.0.0.1:8080.

## Capturas

| Vista | Claro | Oscuro |
| --- | --- | --- |
| Comercio, 1440 px | [Captura](../evidencias/frontend-fe01/comercio-claro-1440.png) | [Captura](../evidencias/frontend-fe01/comercio-oscuro-1440.png) |
| Repartidor, 390 px | [Captura](../evidencias/frontend-fe01/repartidor-claro-390.png) | [Captura](../evidencias/frontend-fe01/repartidor-oscuro-390.png) |

## Comprobaciones

`npm run lint`, `npm run build`, `npm run test:design` y `npm run test:design:e2e`. Las pruebas de navegador usan Chromium, axe, ambos temas y anchos 360/390/768/1024/1440. Incluyen teclado, persistencia, almacenamiento bloqueado, tema previo a React, estados y formularios simulados; rechazan solicitudes externas o a API. Se conservan `npm test` y `npm run test:e2e` para la aplicación funcional.

Estas comprobaciones no certifican accesibilidad completa: falta revisión humana con lector de pantalla y aprobación estética. La integración real, autenticación, heartbeat, cursores y reintentos del nuevo diseño quedan para etapas posteriores. Resultados en [validación](../validation.md).

SPEC-08 incorpora una [vista geográfica con API real](../geo/README.md) accesible desde :8080; las demás pantallas de este prototipo conservan sus fixtures.
