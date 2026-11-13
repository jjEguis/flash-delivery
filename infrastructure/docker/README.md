La definición Docker Compose vive en la raíz. MiniStack y Redis usan imágenes públicas; `cdk-dev` se construye con el Dockerfile de raíz y se activa mediante `--profile dev`. Ningún contenedor monta el socket Docker.

El flujo reproducible está en [la guía del entorno](../../docs/ENTORNO_LOCAL.md).
