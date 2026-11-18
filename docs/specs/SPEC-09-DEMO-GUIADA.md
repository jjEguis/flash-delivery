# SPEC-09 — Demo guiada del ciclo de entrega

Estado: implementada y validada localmente; pendiente revisión del PR. Base: develop después del merge de SPEC-08 v2.

## Problema y alcance

La demo exige conocer pasos que la interfaz no explica: separar sesiones, habilitar perfiles, seleccionar dos coordenadas y volver a iniciar el simulador tras recoger. Un punto de mapa incompleto se descarta silenciosamente y el simulador puede conservar una geometría de la fase anterior.

Este incremento guía el flujo existente sin crear nuevos permisos ni saltarse la aprobación administrativa. No añade listado administrativo, autenticación de producción, notificaciones o geocodificación.

## Criterios de aceptación

1. El acceso explica cómo probar registro/habilitación con usuarios nuevos y cómo separar sesiones. No se publican secretos configurados; el código local de ejemplo permanece solo en la guía de ejecución.
2. La espera de habilitación muestra un identificador seleccionable, explica los pasos administrativos y permite consultar otra vez el estado.
3. Seleccionar solo una recogida o destino bloquea la publicación, muestra un error tras el intento y dirige el foco al mensaje. Se permite publicar sin coordenadas explícitamente; datos numéricos y mapa son alternativas de entrada.
4. La vista del repartidor muestra siguiente acción por fase. Sin puntos en el pedido no permite iniciar simulación vial, pero permite GPS/flujo por estados; explica cómo crear otro pedido con puntos.
5. Al cambiar ASSIGNED → PICKED_UP se detiene la simulación de la fase anterior y se descarta su geometría. Iniciar la nueva fase parte de la última posición aceptada o, si caducó, de un inicio elegido explícitamente. No reinicia en el origen de la primera fase ni cambia estados por GPS.
6. Pausa/reanudación/reinicio conservan velocidad y límites de frecuencia, sin envíos superpuestos ni respuestas de otra fase. Finalizar un recorrido indica recoger o entregar manualmente.
7. Las acciones de estado no se duplican mientras están pendientes y conservan la clave idempotente ante resultado incierto.
8. Prueba de navegador con API real y sesiones separadas: registrar comercio/repartidor nuevos, habilitarlos desde administración, publicar, aceptar, simular ambas fases y completar desde la interfaz. Datos aislados y limpieza acotada, sin borrar pedidos del usuario.
9. Conservar tests previos, ambos temas, accesibilidad y compilación normal sin controles de simulación. Actualizar estado/evidencias, commit y PR hacia develop.

## Diseño previo

Se aplican frontend-design y modern-web-guidance. Se mantienen superficie #ffffff, fondo #f6f8f8, tinta #132c2b, verde #087d62, azul recogida #2a5fa5 y rojo entrega #aa3947; oscuro y Manrope existentes. Texto e instrucciones alineados a izquierda. Guía desplegable junto al acceso; instrucciones al lado de la acción de fase; coordenadas en un fieldset de dos grupos. En móvil se apilan.

```text
Acceso                 Pedido / recorrido
Rol y usuario          Dirección + puntos opcionales
Guía desplegable       Siguiente acción según fase
                       Mapa | compartir y controles
```

Revisión: se descarta añadir una portada o asistente paralelo; la orientación aparece donde se toma cada decisión. No hay nuevos tokens visuales ni animaciones decorativas. La validación de puntos se comunica después de intentar publicar, con foco en el mensaje; los botones auxiliares tienen type=button.

## Validación

Compilación normal/local, lint y unitarios frontend: correctos (22 + 7). Navegador: regresión funcional 10, interfaz unificada 62, mapas y estados 20, producción/referrer 2. Con API real: 2 pruebas aprobadas; la nueva completó registro, aprobación administrativa y ambas fases por UI en 49.4 s. Ver resultados y límites en [validación](../validation.md) y [guía de demo](../demo/README.md).

Se consultaron las guías `forms` y `accessible-error-announcement` de modern-web-guidance. Los auxiliares no envían el formulario, el error de selección incompleta aparece tras enviar y recibe foco, y aria-invalid se sincroniza con user-invalid para coordenadas nativas. Se conserva el diseño aprobado según frontend-design. No se cambiaron endpoints, estados, permisos, tablas ni GSIs. Las pruebas Python de negocio no se repitieron porque sus módulos no cambiaron; las dos pruebas de navegador utilizaron la API local real. El script auxiliar solo reserva IDs de prueba y limpia sus datos.
