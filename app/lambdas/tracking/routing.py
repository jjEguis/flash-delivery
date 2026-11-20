"""Puerto vial y adaptador OSRM privado. Ningún endpoint público de demostración."""
import json
import logging
import math
import os
import time
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


logger=logging.getLogger("flashdelivery.routing")
logger.setLevel(logging.INFO)


class RoutingUnavailable(Exception):
    pass


class RoutingProvider(Protocol):
    def route(self, origin, destination): ...


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


class OsrmRoutingProvider:
    def __init__(self, url=None, timeout=None):
        self.url = (url or os.getenv('OSRM_URL', 'http://osrm:5000')).rstrip('/')
        self.timeout = float(timeout or os.getenv('OSRM_TIMEOUT_SECONDS', '3'))

    def route(self, origin, destination):
        coords = ';'.join(f"{p['longitude']},{p['latitude']}" for p in (origin, destination))
        url = f'{self.url}/route/v1/driving/{coords}?overview=full&geometries=geojson&steps=true&annotations=duration,distance&radiuses=100;100'
        started = time.perf_counter()
        outcome = 'unavailable'
        try:
            with urlopen(url, timeout=self.timeout) as response:
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ValueError('Respuesta excesiva')
                data = json.loads(raw)
            if data.get('code') != 'Ok' or not data.get('routes'):
                raise ValueError('NoRoute')
            route = data['routes'][0]
            geometry = route['geometry']
            coordinates = geometry['coordinates']
            if geometry['type'] != 'LineString' or not 2 <= len(coordinates) <= 20000:
                raise ValueError('Geometría inválida')
            for p in coordinates:
                if len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) or abs(p[0]) > 180 or abs(p[1]) > 90:
                    raise ValueError('Punto inválido')
            durations = [v for leg in route['legs'] for v in leg['annotation']['duration']]
            distances = [v for leg in route['legs'] for v in leg['annotation']['distance']]
            if len(durations) != len(coordinates)-1 or len(distances) != len(durations) or not all(finite(v) for v in durations+distances+[route['distance'], route['duration']]):
                raise ValueError('Anotaciones inválidas')
            # No transmitir geometría duplicada, nombres o estructuras arbitrarias del proveedor.
            steps = [{'distanceMeters':s['distance'], 'durationSeconds':s['duration'],
                      'type':s['maneuver']['type'], 'modifier':s['maneuver'].get('modifier', ''),
                      'location':s['maneuver']['location']} for leg in route['legs'] for s in leg['steps']]
            outcome = 'ok'
            return {'geometry':geometry, 'distanceMeters':route['distance'], 'durationSeconds':route['duration'],
                    'segmentDurations':durations, 'segmentDistances':distances, 'steps':steps}
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, OverflowError, KeyError, TypeError, IndexError) as exc:
            raise RoutingUnavailable('No se pudo calcular una ruta vial') from exc
        finally:
            logger.info(json.dumps({'event':'routing_call', 'outcome':outcome,
                'durationMs':round((time.perf_counter()-started)*1000, 2)}))
