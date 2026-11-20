"""Snapshots Redis por fase, progreso ordenado y recálculo con lock/cooldown."""
from datetime import datetime, timezone
import json
import logging
import os
import secrets
import time

from redis.exceptions import RedisError
from lambdas.orders.repository import OrdersRepository
from lambdas.tracking.coordinates import degrees
from lambdas.tracking.location_store import RedisLocationStore
from lambdas.tracking.progress import project
from lambdas.tracking.routing import OsrmRoutingProvider, RoutingUnavailable
from lambdas.tracking.service import ACTIVE, _own_order, _read_order, _dependency
from lambdas.tracking.repository import TrackingRepository
from lambdas.shared.exceptions import NotFoundError

UPDATE = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local old = cjson.decode(raw)
local new = cjson.decode(ARGV[1])
if old.routeVersion ~= new.routeVersion or (old.sampleEpoch or 0) >= new.sampleEpoch then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""
PUBLISH_ROUTE = """
if redis.call('GET', KEYS[2]) ~= ARGV[1] then return 0 end
local raw = redis.call('GET', KEYS[1])
if raw then
  if cjson.decode(raw).routeVersion ~= ARGV[2] then return 0 end
elseif ARGV[2] ~= '' then return 0 end
local latest = redis.call('GET', KEYS[3])
if not latest or cjson.decode(latest).epoch ~= tonumber(ARGV[4]) then return 0 end
redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[5])
return 1
"""
RELEASE = "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end return 0"


def route_key(order_id, phase):
    return f'tracking:order:{order_id}:route:{phase}'


def clear_routes(client, order_id):
    client.delete(*(route_key(order_id, phase) for phase in ACTIVE), f'tracking:order:{order_id}:routing-cooldown')


def _load(client, key):
    raw = client.get(key)
    return json.loads(raw) if raw else None


def _snapshot(adapter, client, order, point, provider=None):
    phase, order_id = order['status'], order['orderId']
    if phase not in ACTIVE or 'pickupCoordinates' not in order:
        return None
    key = route_key(order_id, phase)
    ttl = int(os.getenv('ROUTE_TTL_SECONDS', '300'))
    cached = _load(client, key)
    if cached and point['epoch'] > cached.get('sampleEpoch', 0):
        update = {**cached, **project(cached, point, cached)}
        client.eval(UPDATE, 1, key, json.dumps(update), ttl)
        cached = _load(client, key)
    recalculate = not cached or cached.get('deviationCount', 0) >= 3 or time.time()-cached['calculatedEpoch'] > ttl
    if not recalculate:
        return cached
    lock = f'tracking:order:{order_id}:routing-lock'
    nonce = secrets.token_hex(16)
    if not client.set(lock, nonce, nx=True, ex=max(10, int(float(os.getenv('OSRM_TIMEOUT_SECONDS', '3')))+5)):
        return cached
    try:
        # Otra invocación pudo publicar mientras se adquiría el lock.
        current = _load(client, key)
        if current and (not cached or current['routeVersion'] != cached['routeVersion']):
            return current
        cooldown = f'tracking:order:{order_id}:routing-cooldown'
        # El cambio de fase puede calcular sin esperar el cooldown de la fase anterior.
        if client.get(cooldown) == phase:
            return cached
        client.set(cooldown, phase, ex=int(os.getenv('ROUTE_RECALCULATE_SECONDS', '30')))
        destination = degrees(order['pickupCoordinates' if phase == 'ASSIGNED' else 'dropoffCoordinates'])
        try:
            # Contador efímero de llamadas, sin coordenadas ni identidad de participantes.
            metric = f'tracking:order:{order_id}:routing-calls'
            count = client.incr(metric)
            if count == 1:
                client.expire(metric, ttl)
            route = (provider or OsrmRoutingProvider()).route(point, destination)
        except RoutingUnavailable:
            return {**cached, 'stale':True} if cached else None
        # No publicar una ruta calculada para una asignación/fase que ya terminó.
        official = _read_order(OrdersRepository(adapter), order_id)
        latest = RedisLocationStore(client).latest(order_id)
        if official['status'] != phase or official.get('courierId') != order.get('courierId') or not latest or latest.get('epoch') != point['epoch']:
            return cached
        route.update(phase=phase, routeVersion=secrets.token_hex(12),
                     calculatedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                     calculatedEpoch=time.time(), stale=False)
        route.update(project(route, point))
        from lambdas.tracking.location_store import location_key
        accepted = client.eval(PUBLISH_ROUTE, 3, key, lock, location_key(order_id), nonce,
                               cached['routeVersion'] if cached else '', json.dumps(route), point['epoch'], ttl)
        if not accepted:
            return _load(client, key)
        # Retirar snapshot de la fase anterior, manteniendo DynamoDB como autoridad.
        for other in ACTIVE - {phase}:
            client.delete(route_key(order_id, other))
        return route
    finally:
        client.eval(RELEASE, 1, lock, nonce)


def advance_safely(adapter, client, order, point):
    try:
        _snapshot(adapter, client, order, point)
    except (RedisError, ValueError, TypeError):
        logging.getLogger(__name__).warning('route_progress_unavailable')


def get_route(adapter, client, *, actor=None, order_id=None, token=None, provider=None):
    reader = OrdersRepository(adapter)
    if token is not None:
        order = TrackingRepository(reader).resolve_order(token, location=True)
        if order is None:
            raise NotFoundError('Seguimiento no encontrado', 'TRACKING_NOT_FOUND')
        order_id = order['orderId']
    else:
        order = _own_order(reader, actor, order_id)
    result = {'orderId':order_id, 'status':order['status'], 'route':None, 'points':None}
    if order['status'] not in ACTIVE:
        return result
    if 'pickupCoordinates' in order:
        result['points'] = {'pickup':degrees(order['pickupCoordinates']), 'dropoff':degrees(order['dropoffCoordinates'])}
    point = _dependency(lambda: RedisLocationStore(client).latest(order_id))
    snapshot = None
    if point and 'epoch' in point and point.get('courierId') == order.get('courierId') and time.time()-point['epoch'] <= int(os.getenv('LOCATION_TTL_SECONDS', '120')):
        snapshot = _dependency(lambda: _snapshot(adapter, client, order, point, provider))
    official = _read_order(reader, order_id)
    if official['status'] != order['status'] or official.get('courierId') != order.get('courierId'):
        result.update(status=official['status'], points=None)
        return result
    if token is not None and TrackingRepository(reader).resolve_order(token, location=True) is None:
        raise NotFoundError('Seguimiento no encontrado', 'TRACKING_NOT_FOUND')
    if snapshot:
        public = {k:v for k,v in snapshot.items() if k not in {'sampleEpoch', 'calculatedEpoch', 'deviationCount'}}
        public['stale'] = snapshot.get('stale', False) or time.time()-point['epoch'] > int(os.getenv('LOCATION_FRESH_SECONDS', '15')) or time.time()-snapshot['calculatedEpoch'] > int(os.getenv('ROUTE_TTL_SECONDS', '300')) or snapshot['deviationCount'] >= 3
        if public['stale']:
            public['etaSeconds'] = None
        if token is not None:
            public.pop('steps', None)
            public.pop('segmentDurations', None)
            public.pop('segmentDistances', None)
        result['route'] = public
    return result
