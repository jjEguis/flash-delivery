"""Tracking geográfico: permisos oficiales primero, Redis como dato prescindible."""
from datetime import datetime, timezone
import math
import os
import re
import time
from typing import Protocol

from redis.exceptions import RedisError

from lambdas.identity.contracts import authorize
from lambdas.shared.exceptions import ConflictError, DependencyUnavailableError, ForbiddenError, NotFoundError, ValidationError, DomainError
from lambdas.tracking.access import TrackingAccess
from lambdas.tracking.repository import TrackingRepository
from lambdas.tracking.location_store import LocationStore
from lambdas.orders.repository import OrdersRepository

ACTIVE = {"ASSIGNED", "PICKED_UP"}


class OrderReader(Protocol):
    def get_order(self, order_id): ...


class LocationValidationError(ValidationError):
    status = 422
    code = "INVALID_LOCATION"


class LocationRateLimit(DomainError):
    status = 429
    code = "LOCATION_RATE_LIMITED"


def validate_point(body, now):
    if not isinstance(body, dict) or body.keys() - {"latitude", "longitude", "accuracyMeters", "recordedAt", "source"}:
        raise LocationValidationError("La ubicación contiene campos no admitidos")
    for name, lower, upper in (("latitude", -90, 90), ("longitude", -180, 180), ("accuracyMeters", 0, float('inf'))):
        value = body.get(name)
        if value is None and name == "accuracyMeters" and name not in body:
            continue
        try:
            valid = type(value) in (int, float) and math.isfinite(float(value)) and lower <= value <= upper
        except OverflowError:
            valid = False
        if not valid:
            raise LocationValidationError(f"{name} fuera de rango")
    if not isinstance(body.get("source"), str) or body.get("source") not in {"SIMULATED", "BROWSER_GPS"}:
        raise LocationValidationError("source debe ser SIMULATED o BROWSER_GPS")
    raw = body.get("recordedAt")
    try:
        if not isinstance(raw, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', raw):
            raise ValueError()
        stamp = datetime.fromisoformat(raw[:-1] + '+00:00')
        if stamp.utcoffset().total_seconds() != 0:
            raise ValueError()
        epoch = stamp.timestamp()
    except (ValueError, OverflowError, AttributeError) as exc:
        raise LocationValidationError("recordedAt debe ser un timestamp UTC con sufijo Z") from exc
    if not now - 120 <= epoch <= now + 15:
        raise LocationValidationError("La muestra es demasiado antigua o futura")
    return {**body, "recordedAt": stamp.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'), "epoch": epoch}


def _read_order(reader: OrderReader, order_id):
    try:
        order = reader.get_order(order_id)
    except ValueError as exc:
        raise ValidationError("orderId inválido") from exc
    if order is None:
        raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")
    return order


def _own_order(reader: OrderReader, actor, order_id, *, write=False):
    authorize(actor, *(('COURIER',) if write else ('STORE', 'COURIER')))
    order = _read_order(reader, order_id)
    if write and order.get('courierId') != actor.courier_id:
        raise ForbiddenError("Solo el repartidor asignado puede compartir ubicación")
    if not write and not ((actor.role == 'STORE' and order['storeId'] == actor.store_id) or
                         (actor.role == 'COURIER' and order.get('courierId') == actor.courier_id)):
        raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")
    return order


def _dependency(operation):
    try:
        return operation()
    except (RedisError, ValueError, TypeError) as exc:
        raise DependencyUnavailableError("La ubicación no está disponible; puedes seguir los estados del pedido") from exc


def publish(adapter, store: LocationStore, actor, order_id, body, *, reader: OrderReader | None = None):
    now = time.time()
    reader = reader or OrdersRepository(adapter)
    order = _own_order(reader, actor, order_id, write=True)
    if order['status'] not in ACTIVE:
        raise ConflictError("Solo se comparte ubicación durante una entrega activa", "LOCATION_NOT_ACTIVE")
    point = validate_point(body, now)
    accepted = _dependency(lambda: store.publish(order_id, actor.courier_id, point, now))
    if accepted == -1:
        raise LocationRateLimit("Espera al menos tres segundos antes de enviar otra ubicación")
    # Cierra la carrera con una finalización concurrente; ningún GET revela muestras de pedidos terminales.
    current = _read_order(reader, order_id)
    if current['status'] not in ACTIVE or current.get('courierId') != actor.courier_id:
        _dependency(lambda: store.clear(order_id))
        raise ConflictError("La entrega ya no está activa", "LOCATION_NOT_ACTIVE")
    return {"orderId": order_id, "recordedAt": point['recordedAt'], "accepted": accepted == 1}


def latest(adapter, store: LocationStore, *, actor=None, order_id=None, token=None, reader: OrderReader | None = None):
    reader = reader or OrdersRepository(adapter)
    if token is not None:
        order = TrackingRepository(OrdersRepository(adapter)).resolve_order(token, location=True)
        if order is None:
            raise NotFoundError("Seguimiento no encontrado", "TRACKING_NOT_FOUND")
        order_id = order['orderId']
    else:
        order = _own_order(reader, actor, order_id)
    result = {"orderId": order_id, "status": order['status'], "updatedAt": order['updatedAt'],
              "location": None, "freshness": "UNAVAILABLE"}
    if order['status'] not in ACTIVE:
        return result
    point = _dependency(lambda: store.latest(order_id))
    if not point or 'stoppedAt' in point or point.get('courierId') != order.get('courierId'):
        return result
    # Revalida estado oficial antes de entregar coordenadas; no hay transacción distribuida Redis/DDB.
    current = _read_order(reader, order_id)
    if current['status'] not in ACTIVE:
        result['status'] = current['status']
        result['updatedAt'] = current['updatedAt']
        return result
    result['location'] = {key: point[key] for key in ('latitude', 'longitude', 'accuracyMeters', 'recordedAt', 'source') if key in point}
    result['freshness'] = 'FRESH' if time.time() - point['epoch'] <= int(os.getenv('LOCATION_FRESH_SECONDS', '30')) else 'STALE'
    return result


def stop(adapter, store, actor, order_id):
    _own_order(OrdersRepository(adapter), actor, order_id, write=True)
    _dependency(lambda: store.stop(order_id, time.time()))


def revoke(adapter, actor, order_id):
    authorize(actor, 'STORE')
    _own_order(OrdersRepository(adapter), actor, order_id)
    access = TrackingAccess(adapter)
    if access.for_order(order_id) is None:
        raise NotFoundError("Este enlace histórico no permite ubicación", "TRACKING_NOT_FOUND")
    access.revoke(order_id)


def clear_finished(client, order_id):
    # Best effort: un fallo Redis nunca revierte la transición oficial.
    try:
        from lambdas.tracking.location_store import RedisLocationStore
        RedisLocationStore(client).clear(order_id)
    except RedisError:
        import logging
        logging.getLogger(__name__).warning('location_cleanup_unavailable')
