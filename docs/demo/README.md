# Prueba guiada de una entrega

Con los servicios ya levantados, abrir http://127.0.0.1:8080/. En el acceso está «Cómo probar la entrega completa». Preparación del entorno: [guía GEO](../geo/README.md).

## Sesiones y registro

Usar tres sesiones independientes: comercio en ventana normal, repartidor en incógnito y administrador en otro perfil o navegador. Dos pestañas del mismo perfil comparten la sesión; cambiar el usuario en una puede detener el envío en la otra.

1. Elegir Comercio, entrar con un usuario nuevo (por ejemplo `comercio_prueba_01`) y registrar nombre/zona. Cambiar el sufijo en cada prueba nueva. No hay contraseñas de cuenta en este adaptador local.
2. Repetir como Repartidor con otro usuario nuevo y **la misma zona**.
3. Cada perfil espera habilitación y muestra «Identificador para el administrador». Se puede seleccionar y copiar con teclado.
4. En la sesión administrativa, elegir Administración y entrar como `admin`. El código local de ejemplo es `admin-local`; si se configuró `DEV_ADMIN_CODE`, usar ese valor. Es un acceso de desarrollo, no autenticación de producción.
5. En Comercios/Repartidores, filtrar Pendiente, abrir «Revisar perfil», escribir un motivo, pulsar «Habilitar perfil» y confirmar la decisión. Volver a cada sesión y pulsar «Ya me habilitaron, actualizar».

Las cuentas creadas con `scripts.demo` ya están habilitadas: sirven para probar entregas rápidamente, pero no demuestran el paso de aprobación. La bandeja permite revisar solicitudes sin copiar el ID; el formulario manual sigue disponible como alternativa. [Guía de aprobaciones y migración](../admin/README.md).

## Publicar y recorrer

1. Comercio: escribir las direcciones y abrir «Seleccionar puntos en el mapa». Usar «Usar puntos de demo de Santa Marta», o elegir recogida y entrega en mapa/coordenadas. Una selección incompleta impide publicar y enfoca el mensaje; Quitar puntos permite un pedido solo por estados.
2. Publicar y conservar el enlace público del destinatario.
3. Repartidor: activar Disponible y aceptar el pedido de la misma zona. Un solo pedido activo por repartidor; finalizar el anterior antes de aceptar otro.
4. Abrir Compartir ubicación. Con simulación seleccionada, elegir «Usar inicio de demo en Santa Marta», consentir e iniciar. Esperar unos segundos a la primera muestra. Para acelerar, usar 25 m/s.
5. Mantener esa vista abierta. Comercio observa el mapa desde el detalle; el destinatario abre su enlace y el mapa público. Sin puntos en el pedido, el simulador explica el bloqueo; GPS y estados siguen disponibles.
6. Al llegar a recogida, el recorrido queda completado y se indica pulsar «Marcar recogido». Esa confirmación cambia el pedido a Recogido y prepara otra ruta. Pulsar **Iniciar simulación** de nuevo: comienza desde la última posición compartida, conservando velocidad y consentimiento. Si la posición ya caducó, elegir un nuevo inicio explícitamente.
7. Al llegar a entrega, pulsar «Marcar entregado». Los mapas dejan de mostrar posición y ruta activa. Ni la llegada del marcador ni la ETA cambian los estados automáticamente.

Pausar no avanza distancia; Reanudar continúa. Reiniciar borra la posición/snapshot de la fase y solicita una ruta desde el inicio elegido. Detener borra la ubicación; salir del mapa también detiene el envío. Una pausa superior a 120 s hace caducar la muestra. «Actualizar recorrido» vuelve a consultar puntos y estado cuando no aparecen.

La ETA usa el perfil automóvil de OSRM sin tráfico real; no es el cronómetro de la demo ni se convierte en una promesa de llegada al cambiar su velocidad.

## Resultados esperados y fallos

| Situación | Acción |
| --- | --- |
| Perfil en revisión | Administrador habilita el ID y el actor actualiza |
| Pedido no aparece | Verificar zona, disponibilidad, perfil habilitado y páginas de abiertos |
| Simulación deshabilitada | Leer el motivo junto al botón: faltan puntos, consentimiento, inicio o confirmar la fase |
| Sin ruta vial | Actualizar recorrido y revisar ambos puntos; OSRM debe estar sano. Crear otro pedido si el actual no tiene puntos |
| Confirmación incierta | Revisar el estado recuperado; si no cambió, reintentar el mismo botón conserva la intención |
| Mapa sin fondo | El texto/estado siguen funcionando; verificar proveedor de tiles y recargar tras cambios de política del servidor |

## Prueba automatizada real

```bash
npm --prefix frontend run build:local
cd frontend
npm run test:geo:real
```

Requiere Python local con boto3/python-dotenv (`GEO_PYTHON` permite elegirlo), MiniStack/Redis/OSRM y :8080. `journey.spec.js` usa actores nuevos, registra y habilita por UI, publica con coordenadas, acepta y completa ambas fases. No se preaprueban perfiles. Los fixtures viven en archivos privados temporales, registran los IDs/intenciones de esta prueba y limpian solo sus claves, incluida presencia en la zona utilizada. No usar `scripts.demo --clean` para limpiar una prueba del usuario con pedidos activos.
