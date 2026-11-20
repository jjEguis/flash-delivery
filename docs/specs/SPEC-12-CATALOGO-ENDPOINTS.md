# SPEC-12 — Catálogo de endpoints

Fecha: 2026-11-19. Base: develop `1d5bced`, con SPEC-11 fusionada mediante PR #16. Estado: implementada y validada; pendiente revisión del PR.

## Solicitud y alcance

Crear un documento legible con todos los endpoints de la aplicación y sus contratos. Por solicitud separada en la misma sesión, limpiar los datos locales de comercios, repartidores, pedidos y derivados, conservando acceso administrativo. No corregir la demo GPS ni presentar su funcionamiento como validado.

## Entregable

[Catálogo completo](../api/ENDPOINTS.md): 40 operaciones de nueve módulos más tres sondas, tablas por módulo, acceso/rol, path/query/header, cuerpos y ejemplos, respuestas declaradas, reglas de estado, idempotencia y secuencia de uso sin geografía. Se enlazan OpenAPI, registro de rutas y stack como evidencia del inventario.

No añadir endpoints, lógica de eliminación a la aplicación ni un script destructivo permanente. La limpieza es mantenimiento explícito del entorno local autorizado por el usuario; no modifica esquema, configuración ni credenciales administrativas. ADMIN es identidad/configuración de desarrollo, no un ítem DynamoDB.

## Aceptación

- Catálogo contiene una ficha para cada operación del registro y las tres sondas reales; contraste exacto con OpenAPI/stack.
- Permisos y reglas contrastados con handlers/servicios. No confundir cancelar con borrar, ubicación con estado, token público con Bearer ni credencial administrativa con perfil persistido.
- Comprobar Markdown, enlaces locales, parámetros y pruebas de contrato. No crear perfiles/pedidos para presentar evidencia con datos luego de la limpieza.
- Registrar conteos de limpieza y resultados reales en docs/validation.md sin tokens, claves privadas ni IDs personales.
- Actualizar índices/estado y entregar commit, rama y PR a develop sin fusionarlo.
