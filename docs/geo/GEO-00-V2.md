# GEO-00 v2 — Compatibilidad y discrepancias

Antes de GEO-02, el **2026-11-17** se levantó MiniStack `ministackorg/ministack:1.5.36` y Redis `7.4.2-alpine`, se provisionó con CDK y `tests/integration/test_api_flow.py -m integration` obtuvo **2 passed (10.18 s)**. Se verificó login, perfiles, habilitación, creación, aceptación competitiva, recogida, entrega, tracking y caché. No se empezó la nueva lógica geográfica sin ese flujo real.

Comprobaciones directas posteriores: DynamoDB ACTIVE, Lambda de tracking Python 3.12 y API Gateway con **37 rutas** (34 de módulos y tres de salud). Se preservaron tabla, índices, handlers `main(event, context)` y estructura del curso. Lua se ejercita con fakeredis y Redis real. No se usó AWS real ni otro emulador.

La versión previa usaba Leaflet y ocho puntos ficticios, sin motor vial, coordenadas de pedido, ETA ni desvíos. La sección 13 de la nueva SPEC prevalece: se migra a MapLibre, se conserva el HTTP existente y se añaden rutas `/route`; no se cambia la aceptación transaccional. El prefijo continúa siendo `/api/v1`.

El extracto OSM y OSRM son auxiliares técnicos en Docker; el backend de negocio sigue siendo Lambda. Desde `cdk-dev` y desde la Lambda desplegada se verificó la red privada `http://osrm:5000`. Una ruta de Santa Marta devolvió 31 coordenadas, 1642.6 m y 142.4 s; OSRM no expone un puerto de host. La imagen no contiene wget/curl: el healthcheck usa Bash/TCP y valida una respuesta real con código Ok, bajo timeout Docker.

La nueva persistencia estática del pedido se almacena en E6 (enteros); las muestras GPS permanecen efímeras. Los campos de creación son opcionales y compatibles. Los tokens nuevos existentes siguen revocables, sin tabla/GSI nuevos. Se redujo FRESH de 30 a 15 s y se documentó la restricción de SIMULATED en backend.

Se leyó la skill instalada `frontend-design` antes de construir la interfaz. [Plan y revisión visual](DISENO-V2.md). Referencias primarias consultadas: [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [OSRM 5.27.1](https://github.com/Project-OSRM/osrm-backend/tree/v5.27.1), [MapLibre/Vite y worker](https://github.com/maplibre/maplibre-gl-js/blob/main/docs/index.md), [Geofabrik Colombia](https://download.geofabrik.de/south-america/colombia.html) y [política de tiles OSM](https://operations.osmfoundation.org/policies/tiles/).
