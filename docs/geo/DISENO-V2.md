# Diseño GEO v2 — revisión previa a la interfaz

Se leyó y aplicó `.agents/skills/frontend-design/SKILL.md` antes de construir la interfaz.

La referencia normativa es SPEC-07 v2.1 y el shell funcional aprobado. Se mantienen Manrope para títulos, controles y datos; alineación izquierda, títulos de 27–32 px, datos de ETA de 28 px y texto de 13–16 px. Paleta: superficie #ffffff, fondo #f6f8f8, tinta #132c2b, ruta #087d62, recogida #2a5fa5 y entrega #aa3947; el tema oscuro usa los tokens existentes, con ruta #39d6ab sobre superficie #142226.

La elección principal es el recorrido vial: el mapa ocupa la columna ancha; ETA, distancia y frescura van inmediatamente debajo. Los controles del repartidor y el timeline ocupan la columna lateral; en móvil se apilan. El mapa diferencia ruta recorrida y pendiente, recogida R, entrega E y posición orientada. Centrado automático desactivable y vista completa tienen botones textuales.

```text
Escritorio                    Móvil
Mapa de recorrido | Acciones  Mapa de recorrido
ETA / distancia   | Timeline  ETA / distancia
Última muestra    | Privacidad Acciones / timeline
```

Revisión del plan: no se introducen nuevas tarjetas de métricas ni una portada decorativa. La tipografía, los radios y el shell están fijados por el diseño aprobado; el esfuerzo visual se concentra en leer el recorrido y distinguir muestra GPS, interpolación y demo. Las posiciones de demo son una selección explícita y se etiquetan en todos los mapas. Sin posición se conservan puntos del pedido y alternativa textual, sin inventar un origen. La interpolación sobre geometría vial dura un segundo, termina en la muestra y respeta movimiento reducido.
