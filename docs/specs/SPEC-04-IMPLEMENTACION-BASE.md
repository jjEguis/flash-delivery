# SPEC-04 — Primer incremento vertical

## Alcance
Implementar Identity local de desarrollo, Stores, Couriers y Orders (crear/consultar/listar), sin Dispatch todavía.

## Orden
1. Contratos DTO y ActorContext.
2. Stores: registro, habilitación, consulta.
3. Couriers: registro, zona, habilitación y disponibilidad declarada.
4. Orders: creación transaccional, consulta y listado con GSI1/GSI2.
5. Pruebas de integración, autorización y paginación.

## Aceptación
Un comercio habilitado crea pedido; aparece en lista del comercio y en abiertos de su zona; comercio ajeno no puede consultarlo con privilegios de propietario; evento CREATED y vista de estado existen; requestId repetido no duplica pedido.
