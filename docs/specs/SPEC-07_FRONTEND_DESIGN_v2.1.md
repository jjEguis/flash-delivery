# FlashDelivery — SPEC-07: Diseño UX/UI e implementación del frontend

**Versión:** 2.1 · **Estado:** aprobado como dirección de diseño, pendiente de validación visual con prototipo · **Entorno:** MiniStack local · **Idioma de UI:** español (Colombia)

## 0. Instrucción obligatoria para Codex

**Antes de escribir o modificar código de interfaz, localiza, lee y aplica la skill `frontend-design` instalada en tu entorno.** Sigue su proceso de diseño y verificación. Si la skill no está disponible, informa el bloqueo: no afirmes haberla utilizado ni la sustituyas silenciosamente. Examina el repositorio y la documentación (`README.md`, `ARQUITECTURA_GENERAL.md`, specs, contratos, `.pln`) antes de comenzar. Si hay discrepancias funcionales, prevalecen los contratos backend existentes y se reportan para decisión; esta spec gobierna la presentación, no modifica APIs unilateralmente.

## 1. Producto y actores

FlashDelivery es una plataforma **B2B de logística de última milla**. Los comercios publican solicitudes y los repartidores disponibles en una zona las aceptan. No es un marketplace de productos ni procesa compras del consumidor. El destinatario sigue su pedido mediante enlace seguro; un administrador interviene en validaciones e incidencias, **nunca en el despacho ordinario**.

Prioridad de experiencias: (1) comercio, (2) repartidor, (3) destinatario, (4) administrador. El GPS, mapa en vivo, rutas y geocodificación **no forman parte de esta fase**. No dibujar un mapa ficticio que parezca operativo ni prometer ETA calculada sin backend.

## 2. Dirección visual

**Concepto:** «Control logístico sin fricción». Referencia estilística: dashboards SaaS premium, modernos, sobrios, con aire editorial, tarjetas expresivas y microinteracciones discretas. **No copiar literalmente diseños de terceros.** Conservar la arquitectura de navegación del prototipo HTML proporcionado, pero modernizar su ejecución: menos bordes y sombras, mejor espaciado, tipografía más refinada, indicadores de estado más legibles, iconos SVG consistentes en lugar de emojis y mayor énfasis en tareas.

### Tokens propuestos (ajustables tras revisar la skill)

La interfaz debe implementar **tema claro y tema oscuro desde FE-01**, con igualdad funcional y visual entre ambos. Los tokens siguientes representan el tema claro; los tokens oscuros y el mecanismo de selección se especifican en la sección 2.1.

| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#F6F8F8` | Fondo general |
| `--surface` | `#FFFFFF` | Tarjetas |
| `--ink` | `#132C2B` | Texto principal |
| `--muted` | `#718582` | Texto secundario |
| `--brand` | `#13A884` | Acciones primarias |
| `--brand-dark` | `#0A6D59` | Hover/contraste |
| `--sidebar` | `#102C2B` | Navegación escritorio |
| `--border` | `#E6ECEA` | Separadores sutiles |
| `--warning` | `#B86C18` | Pendientes |
| `--danger` | `#B4434B` | Errores/cancelaciones |
| `--radius-card` | `20px` | Tarjetas principales |
| `--radius-control` | `12px` | Controles |

Tipografía: `Inter` o `Manrope` (con fallback system-ui), tamaños fluidos y escala coherente. Espaciado base de 4/8 px. Iconografía Lucide. Sombras muy suaves, preferir superficies y espacio en blanco. Animaciones 150–250 ms y soporte `prefers-reduced-motion`. No usar degradados en todos los elementos; reservarlos para un bloque destacado.

### 2.1. Temas claro y oscuro — requisito obligatorio

**Ambos temas deben estar completamente implementados, no solo diseñados.** Usar tokens semánticos en CSS y un atributo `data-theme="light" | "dark"` en el elemento raíz, o una solución equivalente que no duplique estilos por componente. No codificar colores de fondo, texto o bordes directamente en componentes.

| Token semántico | Claro | Oscuro | Propósito |
|---|---|---|---|
| `--bg` | `#F6F8F8` | `#0B1417` | Fondo de la aplicación |
| `--surface` | `#FFFFFF` | `#142226` | Tarjetas y paneles |
| `--surface-raised` | `#F0F5F3` | `#1B3033` | Controles, hover y paneles elevados |
| `--ink` | `#132C2B` | `#EDF6F3` | Texto principal |
| `--muted` | `#607671` | `#A7BDB8` | Texto secundario |
| `--brand` | `#0C896C` | `#39D6AB` | Acciones destacadas |
| `--brand-contrast` | `#FFFFFF` | `#06251E` | Texto sobre acciones destacadas |
| `--sidebar` | `#102C2B` | `#0F1D20` | Navegación |
| `--border` | `#DFE9E5` | `#294044` | Separadores |
| `--focus` | `#087F69` | `#69E7C3` | Indicador de foco |
| `--warning` | `#9B5D12` | `#F5BD68` | Estados pendientes |
| `--danger` | `#AA3947` | `#FF8D97` | Error/cancelación |
| `--success` | `#147D60` | `#61DEAE` | Confirmaciones |

Los valores son puntos de partida y deben ajustarse tras verificar contraste WCAG 2.2 AA, incluidos badges, gráficos, placeholders, iconos y estados hover/focus/disabled. El verde del tema oscuro no debe perder legibilidad sobre superficies oscuras. Evitar negro puro y blanco puro como superficies extensas; conservar la estética premium y la misma jerarquía en los dos temas.

**Comportamiento del selector:**

1. Mostrar en la topbar o menú de perfil un control accesible de **Apariencia: Sistema / Claro / Oscuro**, disponible para comercio, repartidor, destinatario y administrador. En móvil debe seguir siendo fácil de encontrar.
2. Valor inicial `system`; respetar `prefers-color-scheme` y reaccionar a sus cambios cuando la preferencia sea `system`.
3. Guardar la selección explícita en `localStorage` con una clave versionada, por ejemplo `flashdelivery:theme:v1`. Si el almacenamiento está bloqueado, mantener el selector operativo en la sesión sin romper la interfaz.
4. Aplicar el tema antes del primer render cuando sea posible para evitar un destello del tema equivocado (FOUC). En SSR futuro, no asumir disponibilidad de `window` durante renderizado servidor.
5. El selector debe comunicar su estado mediante etiqueta y selección visible, no depender solo de un icono sol/luna. No debe cambiar la sesión, el rol ni los datos de negocio.
6. Mantener imágenes, ilustraciones, tablas, formularios, modales, notificaciones, estados de carga/vacío/error y página pública de tracking legibles en ambos temas. Gráficos futuros deberán usar variables semánticas, nunca paletas fijas.
7. Animar cambios de tema con discreción (150–200 ms), desactivar transiciones cuando `prefers-reduced-motion` lo solicite.

**Arquitectura sugerida:** `styles/tokens.css`, `styles/themes.css`, `app/providers/ThemeProvider.tsx`, `components/ui/ThemeSwitcher.tsx`; definir tipo `ThemePreference = 'system' | 'light' | 'dark'` y separar preferencia del tema resuelto. Si el repositorio ya tiene sistema de temas, reutilizarlo en vez de introducir otro.

**Pruebas obligatorias:** comprobar elección explícita, persistencia tras recarga, modo sistema, cambio de preferencia del sistema, ausencia de FOUC apreciable, teclado y lector de pantalla, contraste, vistas a 360/390/768/1024/1440 px y screenshots de las pantallas principales en ambos temas. No aprobar FE-01 si uno de los temas está incompleto.

### Reglas UX innegociables

- Una acción primaria por pantalla. No más de 2–3 acciones prominentes en la primera vista.
- Lenguaje comprensible: «Nueva entrega», «Aceptar entrega», «Marcar como recogido», «Finalizar entrega».
- Estado visible con **texto + color + icono**, nunca solo color.
- Formularios con validación inline, errores accionables, estados de carga y confirmación para operaciones destructivas.
- La navegación por rol debe mostrar solo funcionalidades autorizadas. El selector de rol del demo es **solo para Storybook/mock**, nunca mecanismo de autorización real.
- No inventar métricas, actividad «en tiempo real», datos de mapa ni resultados de operaciones.
- Todas las acciones que cambian datos deben reflejar estados `idle`, `loading`, `success`, `error` y, donde aplique, `conflict`.

## 3. Layout y navegación

**Escritorio ≥ 1024px:** sidebar fija de ~248 px con logotipo, menú de rol y acceso al perfil; topbar con título contextual, notificaciones (solo si existe backend), estado de entorno local discreto y avatar; contenido máximo 1440 px, padding 24–36 px. Dashboard con cabecera de bienvenida, acción principal, 3–4 métricas, tabla/lista principal y actividad contextual.

**Tablet 768–1023px:** sidebar colapsable, tarjetas en 2 columnas, tablas con scroll o vista condensada.

**Móvil < 768px:** navegación compacta y accesible; repartidor **mobile-first** con tarjetas apiladas, barra inferior o menú claro, acciones de gran tamaño y áreas táctiles mínimas de 44×44 px. Formularios de una columna. No esconder información esencial tras hover.

## 4. Pantallas por actor

### 4.1 Comercio — protagonista

| Ruta conceptual | Pantalla | Acción principal | Contenido |
|---|---|---|---|
| `/app/store` | Inicio | Nueva entrega | Métricas reales, entregas recientes, pendientes de asignación, actividad |
| `/app/store/orders` | Mis entregas | Nueva entrega | Buscar, filtrar por estado, ordenar por fecha, paginar, abrir detalle |
| `/app/store/orders/new` | Nueva entrega | Publicar solicitud | Destinatario, teléfono, dirección, zona, tarifa, notas; validación |
| `/app/store/orders/:id` | Detalle | Según estado | Estado, historial, repartidor si asignado, cancelar si elegible, compartir seguimiento |
| `/app/store/analytics` | Estadísticas | Filtrar período | Solo agregados realmente soportados por API |
| `/app/store/settings` | Mi comercio | Guardar cambios | Datos del comercio y preferencias soportadas |

**Flujo crítico:** Inicio → Nueva entrega → Validación → Confirmar publicación → Pedido `PENDING` → Detalle con enlace de seguimiento. La publicación no debe duplicarse ante doble clic/reintento; usar idempotencia conforme al contrato backend.

### 4.2 Repartidor — protagonista (mobile-first)

| Ruta conceptual | Pantalla | Acción principal | Contenido |
|---|---|---|---|
| `/app/courier` | Mi jornada | Activar/desactivar disponibilidad | Estado, entrega activa, accesos rápidos |
| `/app/courier/available` | Entregas disponibles | Aceptar | Zona, recogida, destino textual, tarifa, detalles; refrescar |
| `/app/courier/active` | Mi entrega activa | Recogido / Entregado | Datos imprescindibles, pasos, contacto autorizado |
| `/app/courier/history` | Historial | Ver detalle | Entregas finalizadas, estados y fechas |
| `/app/courier/profile` | Perfil | Actualizar perfil | Datos permitidos por API |

**Flujo crítico:** Disponible → Explorar → Ver detalles → Aceptar → `ASSIGNED` → `PICKED_UP` → `DELIVERED`. Si otro repartidor acepta antes, HTTP **409**: mostrar «Esta entrega ya fue aceptada», quitarla de disponibles y permitir continuar. Si ya tiene entrega activa, bloquear nueva aceptación con mensaje útil. No simular asignación exitosa sin respuesta confirmada.

### 4.3 Destinatario — acceso público restringido

Ruta `/track/:token`. Página sin sidebar, sin cuenta. Mostrar marca del comercio si está disponible, número de referencia limitado, estado actual, línea de tiempo y última actualización. No exponer datos sensibles, identidad completa del repartidor ni dirección completa salvo autorización expresa del contrato. Token opaco y difícil de adivinar; manejar token inválido/expirado con mensaje neutral. Sin GPS por ahora.

### 4.4 Administrador — secundario

Rutas bajo `/app/admin`: resumen operativo, comercios, repartidores, incidencias. Enfocar en verificación, suspensión/reactivación y gestión de excepciones **solo si existen contratos backend**. No priorizar este panel frente a comercio/repartidor ni inventar endpoints. Separar claramente acciones administrativas con confirmación y auditoría cuando aplique.

## 5. Componentes y patrones reutilizables

`AppShell`, `Sidebar`, `Topbar`, `PageHeader`, `MetricCard`, `OrderStatusBadge`, `OrderTable`, `OrderCard`, `DeliveryTimeline`, `EmptyState`, `ErrorState`, `Skeleton`, `ConfirmDialog`, `Toast`, `SearchField`, `FilterBar`, `Pagination`, `FormField`, `AvailabilityToggle`, `CopyTrackingLink`, `RoleGuard`.

Construir primero primitivas accesibles y luego composiciones por funcionalidad. Estados visuales consistentes para `PENDING`, `ASSIGNED`, `PICKED_UP`, `DELIVERED`, `CANCELLED`, `FAILED`; no permitir transiciones no admitidas por el backend.

## 6. Arquitectura técnica frontend

**React + TypeScript + Vite**, React Router, TanStack Query para server state, React Hook Form + Zod para formularios (si no hay stack ya establecido). CSS con tokens y componentes reutilizables; Tailwind es opcional según repositorio y skill, evitar mezclar múltiples sistemas visuales. `fetch` o cliente HTTP centralizado con tipos y normalización de errores. No acceder a DynamoDB ni Redis directamente desde el navegador.

```text
frontend/src/
  app/               # router, providers, layouts, guards
  features/
    auth/ stores/ couriers/ orders/ dispatch/
    availability/ tracking/ analytics/ admin/
  components/
    ui/ layout/ feedback/
  lib/               # api client, config, error mapping
  styles/            # tokens, globals
  mocks/             # fixtures y adaptadores solo de desarrollo
  tests/
```

Los módulos del frontend se organizan por **features**, pero las dependencias de negocio se materializan mediante endpoints/DTO definidos por los contratos del backend. No duplicar reglas críticas en el cliente: autorización, disponibilidad definitiva y asignación son responsabilidad del servidor.

## 7. Contratos e integración con MiniStack

Configurar `VITE_API_BASE_URL` para API Gateway emulado. No incrustar hosts ni secretos. Mantener una capa de API con funciones tipadas por caso de uso y un adaptador mock **explícito y desactivado en modo integrado**. Leer `openapi.yaml` y `CONTRATOS.md` del repositorio como fuente de verdad para rutas, payloads, estados y errores. Si faltan contratos, crear una lista de discrepancias y bloquear la integración afectada; no inventar campos como si fueran oficiales.

Mínimos a integrar cuando existan: crear entrega, listar por comercio, detalle, cancelar, listar abiertas por zona, cambiar disponibilidad, aceptar entrega, cambiar estado, historial, seguimiento por token, perfiles y operaciones administrativas. Manejar 400/401/403/404/409/429/500 y fallos de red con mensajes contextualizados. Datos de ejemplo solo en Storybook o modo demo rotulado.

## 8. Accesibilidad, privacidad y calidad

- WCAG 2.2 AA como objetivo: contraste, foco visible, teclado, labels, feedback accesible, landmarks.
- Formatos `es-CO`, COP, fecha/hora locales; evitar asumir datos de ubicación precisa.
- Responsive en 360, 390, 768, 1024 y 1440 px; probar estados vacíos y tablas largas.
- No mostrar seguimiento público con datos privados ni permitir acceso cruzado entre comercios.
- Carga progresiva, skeletons, paginación, revalidación al volver al foco cuando tenga sentido; no hacer polling agresivo.
- Tests unitarios de componentes y mapeo de errores; integración con mocks controlados; E2E para publicar, aceptar (incluido 409), finalizar y seguir entrega.

## 9. Plan de implementación para Codex

**FE-00 — Descubrimiento y propuesta visual.** Leer skill `frontend-design`, inspeccionar repositorio y contratos, evaluar demo HTML, presentar dirección visual/tokens, mapa de rutas y brechas. No codificar funciones backend.

**FE-01 — Design system y shell.** Configurar Vite/TS si falta; **temas claro y oscuro funcionales con selector Sistema/Claro/Oscuro y persistencia**, tokens, iconografía, layouts desktop/mobile, botones, inputs, badges, cards, estados de feedback; construir demo navegable con fixtures claramente identificados.

**FE-02 — Comercio.** Inicio, lista, formulario y detalle, integrando APIs existentes progresivamente.

**FE-03 — Repartidor.** Mobile-first, disponibilidad, abiertas, aceptación, 409, activa, cambios de estado e historial.

**FE-04 — Destinatario.** Seguimiento público por token, sin mapa ni GPS.

**FE-05 — Administrador.** Panel secundario sujeto a contratos disponibles.

**FE-06 — Integración y calidad.** E2E, accesibilidad, responsive, manejo de fallos y documentación.

**Regla de ejecución inicial:** implementar **solo FE-00 y FE-01** hasta aprobación visual. No desarrollar todas las pantallas ni integrar endpoints faltantes de golpe.

## 10. Criterios de aceptación de FE-00/FE-01

1. Codex informa qué skill `frontend-design` leyó y qué principios aplicó.
2. La interfaz muestra una identidad visual moderna y consistente, no un clon literal de Dribbble, **en tema claro y oscuro**. El selector Sistema/Claro/Oscuro funciona y conserva la preferencia.
3. Comercio y repartidor tienen navegación y jerarquía diferenciadas; repartidor funciona cómodamente en móvil.
4. Componentes base incluyen estados `loading`, `empty`, `error`, `disabled` y foco accesible.
5. No hay botones de apariencia funcional que no hagan nada: o tienen acción real/demo identificada o están deshabilitados con explicación.
6. Se puede navegar por un prototipo con datos **claramente simulados** sin confundirlo con la API real.
7. `npm run build`, lint y tests disponibles pasan; se documenta qué se ejecutó y qué no.
8. No se modifica backend, tabla DynamoDB, contratos ni configuración MiniStack sin autorización.

## 11. Entregables

Código frontend, tokens de ambos temas, ThemeProvider y selector de apariencia, componentes base, rutas y pantallas de demostración FE-01, README de ejecución, capturas de escritorio y móvil si el entorno lo permite, resultados de pruebas, lista de dependencias y bloqueos de integración.

## 12. Instrucción breve para iniciar Codex

> Implementa FlashDelivery según `docs/specs/SPEC-07_FRONTEND_DESIGN_v2.md`. **Debes localizar, leer y usar la skill `frontend-design` antes de comenzar**. Revisa el HTML de referencia y los contratos existentes. Ejecuta únicamente FE-00 y FE-01: propuesta visual, design system **con temas claro y oscuro, selector Sistema/Claro/Oscuro, persistencia y respeto a preferencias del sistema**, navegación responsive y prototipo funcional con mocks etiquetados. Prioriza comercio y repartidor, mantén administrador secundario, no implementes GPS y no modifiques backend. Ejecuta build y pruebas, y entrega evidencia de resultados.
