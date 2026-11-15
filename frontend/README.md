# Frontend de FlashDelivery

Aplicación de una sola página, sin dependencias de ejecución ni paso de compilación (`index.html`, `styles.css`, `app.js`, `api.js`, `pagination.js`). La sirve `server.py`, que usa solo la biblioteca estándar de Python y además actúa de proxy en el mismo origen hacia API Gateway en MiniStack. Así el navegador nunca necesita CORS. Node y Playwright se usan únicamente para desarrollo y pruebas.

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
