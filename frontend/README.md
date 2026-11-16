# Frontend de FlashDelivery

Aplicación de una sola página, sin dependencias de ejecución ni paso de compilación (`index.html`, `styles.css`, `app.js`, `api.js`, `pagination.js`). La sirve `server.py`, que usa solo la biblioteca estándar de Python y además actúa de proxy en el mismo origen hacia API Gateway en MiniStack. Así el navegador nunca necesita CORS. Node y Playwright sirven para desarrollo y pruebas; el seguimiento geográfico nuevo se compila con Vite.

```bash
docker compose up -d web          # http://127.0.0.1:8080
```

El servidor lee el `ApiId` de `app/.local/outputs.json` en cada solicitud, por lo que reprovisionar no exige reiniciarlo. Solo reenvía los encabezados `Authorization`, `Content-Type` e `Idempotency-Key`.

## Vistas

| Ruta | Rol | Contenido |
| --- | --- | --- |
| `#/` | público | Elección de rol, inicio de sesión de desarrollo y acceso al seguimiento |
| `#/comercio` | STORE | Alta del comercio, pedidos con filtro por estado y «cargar más» (cursor), publicación de pedidos, detalle con historial y enlace de seguimiento, cancelación, estadística mensual con indicador «Desde Redis / Desde DynamoDB» y repartidores conectados |
| `#/repartidor` | COURIER | Alta, interruptor de disponibilidad, heartbeat cada 20 s, pedidos abiertos e historial con «Cargar más», aceptar, recoger y entregar; refresco sin descartar las páginas cargadas |
| `#/admin` | ADMIN | Habilitar o deshabilitar perfiles, consultar un pedido, marcar FAILED y ver presencia por zona |
| `#/seguimiento/<token>` | público | Pasos del pedido e hitos, sin direcciones ni datos personales |

Cada acción con intención conserva su `Idempotency-Key` hasta recibir un resultado válido: conexión perdida, JSON incompleto y errores transitorios permiten reintentar con la misma clave. Se guardan huellas y claves por actor/operación/cuerpo para recuperarlas al reenviar los mismos datos después de recargar; no se guardan cuerpos ni direcciones. Si el almacenamiento está bloqueado, el respaldo dura solo mientras siga abierta la página. No hay exclusión mutua entre pestañas. La idempotencia transaccional del servidor confirma la unicidad.

## Tests

Desde esta carpeta, con Node 22 y Python 3 disponibles:

```bash
npm ci
npm test                           # unitarios del cliente HTTP y la paginación
npx playwright install chromium
npm run test:e2e                   # escritorio y móvil; API simulada, sin Docker
npm run test:smoke                 # web :8080 y API real provisionada
```

El smoke real consulta salud/zonas y hace login hasta el formulario de alta, sin enviar ese formulario ni crear perfiles/pedidos. Se puede cambiar su origen con `FRONTEND_BASE_URL`. Los demás tests arrancan su servidor aislado en :4173 e interceptan las solicitudes de API. En Linux, Playwright puede requerir `install --with-deps chromium`.

GitHub Actions ejecuta los unitarios y el navegador con API simulada. Los directorios `test-results/` y `playwright-report/` son artefactos locales ignorados. Alcance y criterios en [SPEC-07](../docs/specs/SPEC-07-FRONTEND-FIABILIDAD.md).

## Prototipo de diseño FE-00/FE-01

La entrada independiente `preview.html` usa React, TypeScript y Vite con datos en memoria. Requiere Node 22.12+. Ejecutar `npm ci` y `npm run dev:preview`; abrir http://127.0.0.1:5173/preview.html. `npm run build` genera `design-dist/` y `npm run preview` sirve esa compilación. No requiere API ni Docker. El cliente funcional descrito arriba continúa en :8080.

Código por funcionalidades en `src/features/`, shell y providers en `src/app/`, primitivas en `src/components/`, fixtures en `src/mocks/` y tokens en `src/styles/`. Pruebas adicionales: `npm run lint`, `npm run test:design` y `npm run test:design:e2e`. [Guía de revisión](../docs/frontend/FE-01-REVISION.md) y [decisiones](../docs/frontend/FE-00-DISENO.md). La revisión visual está pendiente antes de iniciar FE-02.

## Seguimiento geográfico real (SPEC-08)

`npm run build:local` añade `design-dist/geo.html`, accesible desde los enlaces de cada pedido en :8080. Usa React, los tokens del diseño aprobado, Leaflet local y la API real. Comercio y destinatario consultan el mapa; el repartidor activa simulación o GPS con consentimiento. Los tokens públicos nuevos caducan y pueden revocarse. Los enlaces históricos siguen mostrando estados, sin permiso geográfico.

`npm run build` genera la versión sin controles de simulación. Pruebas: `npm run test:geo:e2e` (API interceptada), `npm run test:geo:production` (compilación normal previa), `npm run test:geo:real` (MiniStack/Redis/:8080 reales y compilación local previa). Esta última requiere Python local con boto3 y python-dotenv, configurable por `GEO_PYTHON`; crea y elimina sus datos aislados. [Guía completa](../docs/geo/README.md).
