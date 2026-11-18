# Aprobaciones administrativas

1. Registrar un comercio o repartidor nuevo desde su propia sesión. Queda Pendiente.
2. En otra sesión, entrar como ADMIN y abrir Administración. Elegir Comercios o Repartidores, estado Pendiente y Actualizar si se acaba de registrar.
3. Abrir Revisar perfil, comprobar nombre/zona/identificador, escribir el motivo y pulsar Habilitar perfil. Revisar la confirmación y confirmar la decisión.
4. El estado y el historial cambian después de confirmar la escritura. En la sesión del propietario pulsar Ya me habilitaron, actualizar.
5. Para suspender, filtrar Habilitado, revisar el perfil, escribir motivo y confirmar Suspender perfil. Para reactivar, filtrar Suspendido y habilitar de nuevo.

El historial muestra administrador, fecha, motivo y versión. Los cambios anteriores no tienen auditoría. El formulario manual por identificador permanece como alternativa compatible; sus cambios se auditan como «Sin motivo informado (cliente anterior)». Esa alternativa no pide versión ni motivo. Después de usarlo, actualizar la bandeja.

Un repartidor con entrega activa no puede suspenderse: finalizarla o resolverla por los procedimientos del pedido. El backend comprueba la ausencia de ACTIVE junto al cambio de perfil; un error 409 no genera un cambio ni un evento. Reactivar no establece disponibilidad: el repartidor la elige después.

Si otro administrador cambia el perfil, aparece un conflicto y el detalle se vuelve a consultar. Leer el nuevo estado y confirmar otra vez. Repetir el mismo estado ya aplicado no crea otra decisión. Las listas son eventualmente consistentes; Actualizar vuelve a consultar y Cargar más sigue el cursor. Una página vacía puede tener otra página. La consulta no es una fotografía congelada.

## Instalación existente

Provisionar las Lambdas actualizadas y añadir los índices a los perfiles anteriores:

```sh
docker compose exec -T cdk-dev python -m scripts.provision
docker compose exec -T cdk-dev python -m scripts.backfill_approvals --dry-run
docker compose exec -T cdk-dev python -m scripts.backfill_approvals
docker compose exec -T cdk-dev python -m scripts.backfill_approvals --dry-run
```

El script hace Scan paginado solo como mantenimiento; los endpoints usan Query/GetItem. Añade únicamente approvalStatus, GSI2PK y GSI2SK. No cambia permisos, atributos de negocio ni versión. Se puede repetir; si concurrent es mayor que cero, volver a ejecutar para los perfiles omitidos por una modificación simultánea. No borra perfiles ni crea eventos históricos.

Clasificación de datos anteriores: enabled=true es ENABLED; false con versión 1 es PENDING; false con versión posterior es SUSPENDED. Es una inferencia técnica, no prueba de aprobación histórica. Un perfil legado suspendido con ACTIVE requiere reactivación manual para resolver la entrega. Retención de auditoría indefinida en esta demo local; definir política antes de un despliegue de producto.

```sh
cd frontend
npm run build:local
```

Abrir http://localhost:8080 y actualizar la página. La autenticación sigue siendo exclusivamente de desarrollo. El administrador no obtiene acceso a GPS ni tokens de seguimiento por estos endpoints.
