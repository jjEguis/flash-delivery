# Informe de calidad y rendimiento — SPEC-06

Fecha: 2026-11-13. Datos crudos: [`evidencias/benchmark-10k.json`](evidencias/benchmark-10k.json). Script reproducible: `app/scripts/benchmark.py`.

## Entorno de medición

| Elemento | Valor |
| --- | --- |
| Equipo | Intel Core i5-1334U (12 hilos), 12 GB de RAM, Windows 11 con Docker Desktop 29.8.0 (WSL2) |
| Contenedores | cdk-dev (Python 3.12.16), MiniStack 1.5.36, Redis 7.4.2-alpine |
| Datos | 10 000 pedidos sintéticos de un comercio y una zona: 20 017 ítems (META + vista de estado y perfiles) |
| Muestras | 100 por patrón (10 para el Scan, 50 para HTTP); cliente en la misma red de Compose |

```bash
docker compose exec -T cdk-dev python -m scripts.benchmark --orders 10000 --samples 100
```

El script crea un namespace `BENCH_<id>`, mide, guarda `app/.local/benchmark.json` y borra sus 20 406 claves por clave exacta (BatchWriteItem), sin Scan de limpieza.

## Resultados

### Patrones de acceso frente a Scan

| Operación | Ítems leídos | p50 | p95 |
| --- | ---: | ---: | ---: |
| AP03 GetItem del pedido | 1 | 1,8 ms | 2,9 ms |
| AP05 Query GSI1, 25 pedidos más recientes del comercio | 25 | 348,9 ms | 399,0 ms |
| AP06 Query GSI2, 25 pedidos por estado | 25 | 76,0 ms | 93,1 ms |
| AP08 Query GSI2, 25 abiertos de la zona | 25 | 79,4 ms | 92,3 ms |
| Misma necesidad que AP05 con Scan (sin índice) | **20 017** (9 páginas) | 1 444,2 ms | 1 522,4 ms |

Sin índice, obtener los 25 pedidos más recientes obliga a leer toda la tabla, filtrar en la aplicación y ordenar: 800 veces más ítems leídos que la Query. En DynamoDB real el costo de lectura se factura por ítems y tamaño leídos, así que esa diferencia es también de costo. Por eso ninguna ruta operativa usa Scan.

### Caché de estadísticas (Redis, Cache-Aside)

| Lectura | p50 | p95 |
| --- | ---: | ---: |
| Fallo de caché (DynamoDB GetItem + SETEX) | 2,36 ms | 3,45 ms |
| Acierto de caché (GET en Redis) | 0,17 ms | 0,33 ms |

TTL observado: 300 s. Tras cada entrega la clave se invalida, y la siguiente lectura vuelve a DynamoDB (verificado en las pruebas y en la interfaz). Con Redis caído, la lectura cae a DynamoDB (`test_redis_down_returns_503_for_presence_but_not_for_dispatch`).

### Concurrencia: 100 aceptaciones del mismo pedido

| Resultado | Valor |
| --- | --- |
| Ganadores | **1** |
| Rechazos `ORDER_ALREADY_ASSIGNED` (409) | 99 |
| Escrituras parciales | 0 (un solo ACTIVE, dos eventos, ninguna vista huérfana) |
| Tiempo total | 34,9 s; latencia por solicitud p50 11,0 s, p95 12,1 s |

La invariante se cumple siempre: la confirmación la decide la condición sobre la versión de META y la ausencia de `COURIER#id / ACTIVE` dentro de `TransactWriteItems`, no Redis ni una lectura previa. La misma propiedad se valida en `tests/integration/test_concurrency.py` en cada corrida de la suite.

### API HTTP (API Gateway → Lambda en MiniStack)

| Ruta | Primera llamada | p50 | p95 |
| --- | ---: | ---: | ---: |
| `GET /api/v1/health` (Lambda inline) | 77 ms | 54,8 ms | 56,2 ms |
| `GET /api/v1/zones` (Lambda empaquetada) | 64 ms | 55,1 ms | 57,1 ms |

### Pruebas automatizadas

| Suite | Resultado |
| --- | --- |
| Unitarias (moto/fakeredis, sin red) | 100 passed |
| Integración (MiniStack + Redis reales) | 15 passed: infraestructura, AP01–AP12, flujo HTTP completo, 100 aceptaciones concurrentes |
| Total | **115 passed** |

Cubren permisos (401/403 y aislamiento entre comercios), validación (400), paginación con cursores manipulados, idempotencia (replay y 409 `IDEMPOTENCY_CONFLICT`), TTL y miembros vencidos en Redis, caída de Redis y errores internos ocultos.

## Limitaciones de MiniStack

- **Las Query sobre GSI crecen con el tamaño de la partición.** AP05 (partición de 10 000 pedidos) tarda unos 350 ms, mientras AP06/AP08 (particiones de unos 2 000) tardan unos 78 ms, aunque las tres leen 25 ítems. El emulador parece recorrer la partición del índice en cada consulta; en DynamoDB la latencia depende de los ítems devueltos. Las latencias absolutas de este informe **no** representan DynamoDB real; los ítems leídos sí reflejan el diseño.
- **Rendimiento de escritura y concurrencia limitado:** unos 70 ítems/s en carga masiva y unas 60 operaciones/s bajo contención; MiniStack atiende las solicitudes prácticamente en serie. Por eso la carga de 100 000 pedidos (unos 46 minutos estimados) no se ejecutó en este equipo; el script la admite con `--orders 100000`.
- **`ScannedCount` no es fiable en el emulador:** el informe cuenta los ítems devueltos página a página.
- **La consistencia eventual de los GSI** se ve como un retraso breve; las pruebas de integración esperan la convergencia con reintentos acotados. El emulador no reproduce los tiempos reales de propagación.
- **IAM no se aplica en MiniStack:** los roles y permisos del stack se sintetizan, pero no se verifican.

## Conclusiones

- El diseño de tabla única resuelve los doce patrones con GetItem o Query, leyendo solo los ítems que se devuelven. El Scan equivalente lee la tabla completa y su costo crece con el volumen.
- La aceptación competitiva es correcta bajo carga real de 100 hilos: un ganador, sin escrituras parciales y con errores de dominio estables.
- Redis acelera las lecturas repetidas (de 2,4 ms a 0,17 ms) sin convertirse en fuente de verdad: su caída degrada la presencia (503), pero no afecta las asignaciones ni las estadísticas.
- Estos resultados no demuestran que NoSQL sea superior a SQL en general. Muestran que, para patrones de acceso conocidos de antemano, la tabla única con índices dispersos ofrece lecturas acotadas y transacciones atómicas. A cambio, las consultas ad hoc no previstas requieren un índice nuevo o un proceso analítico aparte.
