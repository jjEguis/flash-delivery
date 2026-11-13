# SPEC-00 — Infraestructura local MiniStack

**Estado:** incremento 0 implementado y validado el 2026-11-12; **prioridad:** bloqueante para negocio.

Ejecución y límites en [entorno local](../ENTORNO_LOCAL.md); evidencia en [validación](../validation.md). Incluye Lambda ZIP con dependencias y prueba de persistencia tras reinicio ordenado. No acredita todavía las carreras de aceptación de negocio ni equivalencia con AWS real.

## Objetivo
Entorno local reproducible para DynamoDB, Lambda, API Gateway y Redis sin utilizar AWS real.

## Entradas y restricciones
- Python, Docker Compose, MiniStack, Redis, pytest; CDK sujeto a compatibilidad.
- Leer documentación oficial de la **distribución y versión exactas** de MiniStack antes de elegir imagen, puertos o comandos.
- No reemplazar MiniStack por LocalStack sin autorización.

## Entregables
1. `docker-compose.yml`, `.env.example`, `scripts/` con bootstrap idempotente.
2. Infraestructura que crea `FlashDeliveryTable`, GSI1 y GSI2.
3. Adaptadores Python de DynamoDB y Redis con configuración inyectable.
4. `GET /api/v1/health` a través de API Gateway + Lambda, si está soportado.
5. Pruebas smoke de persistencia, índices, transacciones, Lambda y API Gateway.
6. Matriz de compatibilidad real (funciona/no funciona/no probado, evidencia y comando).

## Pruebas de aceptación
- `docker compose up -d` y `docker compose down` funcionan.
- Escritura/lectura de ítem; consulta GSI; transacción que confirma; transacción que falla por condición sin efectos parciales.
- Redis `PING`, `SET EX`, `ZADD`, `ZRANGE`.
- Endpoint health comprobado o limitación documentada con evidencia.
- No se detectan llamadas a AWS real.

## Bloqueos
Sin soporte verificado de transacciones condicionales no iniciar aceptación competitiva. Si falla API Gateway/Lambda, documentar sustituto temporal solo para pruebas de dominio, sin afirmar cumplimiento del requisito.
