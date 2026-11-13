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
