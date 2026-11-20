# Flujo de entrega por especificación

Por instrucción del usuario, cada SPEC implementada se entrega en GitHub mediante
una rama `feature/spec-XX-descripcion` y un pull request con destino a `develop`.

- Partir de `develop` actualizado para cada nueva SPEC.
- Mantener el cambio acotado a la SPEC y ejecutar las comprobaciones pertinentes.
- Actualizar su estado y evidencias en `docs/specs/` y `docs/validation.md`.
- Crear el commit, publicar la rama y abrir el PR al completar la implementación.
- Describir comportamiento, validación y limitaciones en el PR y entregar su enlace.
- No fusionar el PR sin autorización del usuario.
- Excluir credenciales, `.env`, entornos virtuales y artefactos locales del commit.

SPEC-00 incorpora la base local existente porque aún no estaba versionada.

# Estructura del curso

Por instrucción del usuario, seguir la estructura de paquetes del ejemplo
https://gitlab.com/caov_unimag/bd_no_sql: `app/infra`, `app/lambdas`,
`app/layers/dependencias`, `app/tests`, `app/requirements.txt` y `app/cdk.json`.
Los handlers usan `main(event, context)`. Añadir tests con fixtures compartidos
moto/fakeredis para cada funcionalidad; mantener pruebas reales bajo
`app/tests/integration`, seleccionadas explícitamente. No eliminar pruebas de
integración al añadir mocks. Documentación y especificaciones permanecen en docs/.
