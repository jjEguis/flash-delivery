# Frontend de FlashDelivery

Aplicación de una sola página, sin dependencias ni paso de compilación (`index.html`, `styles.css`, `app.js`). La sirve `server.py`, que usa solo la biblioteca estándar de Python y además actúa de proxy en el mismo origen hacia API Gateway en MiniStack. Así el navegador nunca necesita CORS.

```bash
docker compose up -d web          # http://127.0.0.1:8080
```

El servidor lee el `ApiId` de `app/.local/outputs.json` en cada solicitud, por lo que reprovisionar no exige reiniciarlo. Solo reenvía los encabezados `Authorization`, `Content-Type` e `Idempotency-Key`.

## Vistas

| Ruta | Rol | Contenido |
| --- | --- | --- |
| `#/` | público | Elección de rol, inicio de sesión de desarrollo y acceso al seguimiento |
| `#/comercio` | STORE | Alta del comercio, pedidos con filtro por estado y «cargar más» (cursor), publicación de pedidos, detalle con historial y enlace de seguimiento, cancelación, estadística mensual con indicador «Desde Redis / Desde DynamoDB» y repartidores conectados |
| `#/repartidor` | COURIER | Alta, interruptor de disponibilidad, heartbeat cada 20 s, pedidos abiertos de la zona, aceptar, recoger, entregar e historial |
| `#/admin` | ADMIN | Habilitar o deshabilitar perfiles, consultar un pedido, marcar FAILED y ver presencia por zona |
| `#/seguimiento/<token>` | público | Pasos del pedido e hitos, sin direcciones ni datos personales |

Cada acción de escritura conserva su `Idempotency-Key` hasta recibir una respuesta definitiva: si se pierde la conexión o el servidor responde 5xx, el reintento usa la misma clave y no duplica el pedido ni la transición. El diseño sigue la estructura de tarjetas, chips, opciones seleccionables, botones píldora y recuadro destacado del total, con paleta propia (azul petróleo y coral), modo oscuro y diseño adaptable a celular.
