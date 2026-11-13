# Plan de trabajo — FlashDelivery

Fecha de revisión: 2026-11-12. Alcance de esta entrega: análisis y organización documental; no implementación de negocio ni cambios al entorno en ejecución.

**Actualización posterior:** incremento 0 implementado: cdk-dev, empaquetado ZIP/S3 local, rutas de salud y prueba de persistencia. Consultar [validación](validation.md) y [guía local](ENTORNO_LOCAL.md). El diagnóstico siguiente conserva el estado observado antes de ese incremento; el próximo trabajo corresponde a contratos y primer flujo de negocio.

**Reorganización solicitada:** la implementación ahora sigue `app/infra`, `app/lambdas`, `app/layers/dependencias` y `app/tests` del curso; moto/fakeredis ejecutan los unitarios sin infraestructura. Las diferencias históricas del diagnóstico sobre rutas y cdk-dev ya se resolvieron. Las instrucciones vigentes están en el README y la guía local; la próxima SPEC es SPEC-01, modelo de ítems y accesos DynamoDB.

## 1. Panorama

El dominio es adecuado para demostrar el stack del curso: comercios publican entregas, repartidores de una zona compiten por aceptarlas, un solo repartidor gana y completa el pedido. DynamoDB conserva el estado oficial y las transacciones; Redis aporta presencia temporal y caché Cache-Aside de estadísticas. El MVP excluye pagos, mapas en tiempo real y optimización de rutas.

La arquitectura propuesta es un monolito modular Python con handlers Lambda delgados y casos de uso independientes del transporte. No hace falta convertir cada módulo en un microservicio ni ejecutar llamadas Lambda a Lambda para coordinar transacciones.

## 2. Referencia del curso y estado local

Se revisaron README, Compose, Dockerfile, stack CDK, handlers y caché del [repositorio del curso](https://gitlab.com/caov_unimag/bd_no_sql), commit `835ada8aa75f243b8bc2f5a80fa8cd37519ea5f8`. La revisión de código no acredita ejecución del ejemplo.

| Aspecto | Repositorio del curso | FlashDelivery actual / acción |
| --- | --- | --- |
| Entorno | Emulador, Redis y cdk-dev con Dockerfile | MiniStack y Redis; Python/CDK en host. Añadir cdk-dev para reproducir el flujo del curso |
| Emulador | Compose activo usa LocalStack 4.14 | Mantener MiniStack fijado en 1.5.36 según decisión local; validar compatibilidad específica |
| Despliegue | cdklocal bootstrap/deploy, assets empaquetados | CDK sintetiza y boto3 aplica CloudFormation sin bootstrap; documentar diferencia y verificar flujo requerido para la entrega |
| API | REST API y evento proxy v1 | HTTP API y evento v2; conservar contrato coherente y no copiar eventos ni URLs literalmente |
| Lambdas | CRUD de ejemplo con dependencias empaquetadas | Solo health inline; falta empaquetar backend y dependencias, variables, permisos y rutas de negocio |
| Datos | Ejemplo PK/SK | Tabla con dos GSIs; faltan ítems y repositorios del dominio |
| Redis | Cache-Aside de ítems | Cliente técnico existente; faltan presencia y caché de negocio demostrable |
| Tests | Unitarios con moto/fakeredis | Suite local de infraestructura y contratos de health; faltan casos de uso y carreras de negocio |

No copiar sin adaptación la sugerencia del README de cambiar únicamente la imagen del emulador: el Compose de referencia usa healthcheck, rutas, red y variables de LocalStack. Tampoco trasladar sus comentarios de compatibilidad como evidencia propia de MiniStack.

La validación local histórica registra confirmación del usuario de provisionamiento y suite completa sin fallos. En esta revisión no se levantaron contenedores ni se repitieron integraciones. Persistencia tras reinicio, empaquetado de negocio y acceso a Redis desde una Lambda siguen pendientes de demostración.

## 3. Unificar el diseño antes de codificar

Tomar la arquitectura v1.1 como propuesta de referencia y reconciliar contratos anteriores:

- Estados `PENDING`, `ASSIGNED`, `PICKED_UP`, `DELIVERED`, `CANCELLED`; `FAILED` requiere procedimiento excepcional definido.
- Un solo pedido activo por repartidor, protegido con `COURIER#id / ACTIVE` dentro de DynamoDB.
- Seguimiento público por token; sin escritura de GPS en el MVP.
- Estadísticas mensuales actualizadas transaccionalmente; sin outbox ni consumidor asíncrono necesarios para este alcance.
- Prefijos de claves, DTOs, claves de Redis y nombres HTTP deben ser únicos y coherentes con v1.1. El diseño anterior de `OPEN`, asignación separada y métricas diarias queda como histórico.

## 4. Secuencia recomendada

### Incremento 0 — Cerrar reproducibilidad y ejecución Lambda

Completar SPEC-00 sin rehacer infraestructura ya útil. Añadir Dockerfile/cdk-dev, fijar dependencias y documentar comandos. Probar una Lambda empaquetada que importe código compartido y redis-py, lea DynamoDB y acceda a Redis dentro de la red Compose. Comprobar reinicio con datos de prueba identificables en ambos almacenes y limpieza acotada. Alinear `/health` actual con `/api/v1/health` propuesto, conservando compatibilidad si procede.

Salida: arranque, provisionamiento y prueba HTTP reproducibles; confirmar que la estrategia de assets funciona en MiniStack antes de desarrollar módulos completos. CDK sigue siendo la fuente declarativa de infraestructura.

### Incremento 1 — Datos y contratos del primer flujo

Concretar SPEC-01, SPEC-02 y SPEC-03 para perfiles y creación de pedidos: ejemplos JSON, consultas, condiciones, DTOs, errores y OpenAPI. Definir identidad local verificada mediante credenciales de desarrollo configuradas, con roles ADMIN/STORE/COURIER y pertenencia obtenida del servidor. Precisar habilitación administrativa, zonas, tarifa, idempotencia, token y permisos.

Salida: contratos coherentes para escribir el primer flujo, sin decisiones incompatibles entre documentos. Las especificaciones pueden completarse por incremento; no es necesario construir todos los repositorios anticipadamente.

### Incremento 2 — Primer flujo completo

Implementar Identity local, Stores/Couriers mínimos y Orders. Comercio habilitado crea pedido, lo consulta y lo lista; un repartidor habilitado lo descubre por zona. Crear META, evento, vista de estado y registro idempotente en una transacción.

Salida: demostración HTTP por API Gateway → Lambda → DynamoDB; repetir la misma intención no crea otro pedido; otro comercio no accede al detalle privado; listados paginados sin Scan.

### Incremento 3 — Aceptación competitiva

Implementar Dispatch con constructores transaccionales de los módulos propietarios. Condicionar estado del pedido y habilitación/disponibilidad/zona del repartidor, crear ACTIVE y actualizar eventos, vistas e idempotencia en el mismo commit.

Salida: 100 repartidores compitiendo por un pedido producen un ganador; un repartidor compitiendo por dos pedidos obtiene como máximo uno; sin escrituras parciales ni duplicación ante respuesta perdida.

### Incremento 4 — Ciclo de entrega y Redis

Añadir recogida, entrega y cancelación; liberar ACTIVE solo para el pedido esperado. Implementar heartbeat con TTL/ZSET, limpieza de miembros vencidos, seguimiento mínimo por token y agregado mensual idempotente. Aplicar Cache-Aside a estadísticas, invalidar después del commit y probar miss/hit/expiración y caída de Redis.

Salida: ciclo completo y caché funcional justificada. Un fallo de Redis nunca revierte una asignación confirmada ni permite adjudicar dos veces.

### Incremento 5 — Demo y sustentación

Completar SPEC-06 con resultados reproducibles, latencias y límites del emulador. Después del contrato estable, construir una interfaz sencilla para comercio, repartidor y seguimiento. Preparar seed sintético y guion de demo: publicar, competir, recoger, entregar y mostrar miss/hit en estadísticas.

Salida: código, diseño NoSQL, pruebas, demo y argumentos de arquitectura alineados con los entregables del curso.

## 5. Decisiones que deben cerrarse en los contratos

Identidad local y credenciales; catálogo de zonas; tarifa y moneda; permisos para habilitar perfiles y gestionar FAILED; intervalo/vigencia de heartbeat; retención idempotente; duración, revocación y entrega del token; formato de cursor. Son pendientes de diseño, no funcionalidades ya implementadas.

El hash del token por sí solo no permite localizar el pedido: diseñar explícitamente un token con identificador y secreto o una correspondencia por hash consultable por clave, sin Scan. Resolver también cómo devolver el mismo resultado de creación en reintentos sin almacenar el secreto en claro accidentalmente.

## 6. Cómo comenzar

El siguiente trabajo concreto debe ser el incremento 0 y el contrato mínimo del incremento 1. Después implementar creación y consulta de pedidos como primer flujo completo. La parte más delicada será la aceptación transaccional con idempotencia; conviene validarla antes de invertir en frontend o funcionalidades secundarias.
