"""Availability: presencia efímera de repartidores en Redis (heartbeat + ZSET por zona).

DynamoDB decide quién puede trabajar (habilitado y disponible); Redis solo indica quién
está conectado ahora. La presencia nunca adjudica pedidos ni participa en el commit.
"""
import json
import os
import time

from redis.exceptions import RedisError

from lambdas.availability.repository import AvailabilityRepository, heartbeat_key, zone_key
from lambdas.couriers.service import get_my_courier
from lambdas.identity.contracts import ActorContext, authorize
from lambdas.shared.exceptions import ConflictError, DependencyUnavailableError, ForbiddenError, ValidationError
from lambdas.shared.storage import keys
from lambdas.stores.service import get_my_store


def ttl():
    return int(os.getenv("PRESENCE_TTL_SECONDS", "60"))


def heartbeat(adapter, cache, actor: ActorContext, *, now=None):
    """Renueva la presencia: clave con TTL y score en el ZSET de su zona.

    El servidor fija la hora (no confía en el reloj del dispositivo) y aprovecha para
    retirar del ZSET los miembros vencidos de la zona."""
    authorize(actor, "COURIER")
    courier = get_my_courier(adapter, actor)
    if not courier["enabled"]:
        raise ForbiddenError("Tu perfil aún no está habilitado", "COURIER_NOT_ENABLED")
    if not courier["available"]:
        raise ConflictError("Activa tu disponibilidad antes de conectarte", "COURIER_NOT_AVAILABLE")
    epoch = int(time.time() if now is None else now)
    zone = courier["zoneId"]
    try:
        pipe = cache.pipeline(transaction=True)
        pipe.set(heartbeat_key(actor.courier_id), json.dumps({"zoneId": zone, "lastHeartbeatEpoch": epoch}), ex=ttl())
        pipe.zadd(zone_key(zone), {actor.courier_id: epoch})
        pipe.zremrangebyscore(zone_key(zone), "-inf", epoch - ttl() - 1)
        pipe.execute()
    except RedisError as exc:
        raise DependencyUnavailableError("El servicio de presencia no está disponible") from exc
    return {"courierId": actor.courier_id, "zoneId": zone, "lastHeartbeatEpoch": epoch, "expiresInSeconds": ttl()}


def go_offline(cache, courier_id, zone_id):
    pipe = cache.pipeline(transaction=True)
    pipe.delete(heartbeat_key(courier_id))
    pipe.zrem(zone_key(zone_id), courier_id)
    pipe.execute()


def leave(adapter, cache, actor: ActorContext):
    authorize(actor, "COURIER")
    courier = get_my_courier(adapter, actor)
    try:
        go_offline(cache, actor.courier_id, courier["zoneId"])
    except RedisError as exc:
        raise DependencyUnavailableError("El servicio de presencia no está disponible") from exc


def list_present(adapter, cache, actor: ActorContext, zone_id, page, *, now=None):
    """AP10: repartidores con heartbeat vigente. Comercios solo ven su propia zona."""
    authorize(actor, "STORE", "ADMIN")
    try:
        keys.identifier(zone_id)
    except ValueError as exc:
        raise ValidationError("zoneId inválido") from exc
    if actor.role == "STORE" and get_my_store(adapter, actor)["zoneId"] != zone_id:
        raise ForbiddenError("Solo puedes ver repartidores de tu zona", "ZONE_MISMATCH")
    current = int(time.time() if now is None else now)
    try:
        result = AvailabilityRepository(cache).list_present(zone_id, now=current, window=ttl(), **page)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    except RedisError as exc:
        raise DependencyUnavailableError("El servicio de presencia no está disponible") from exc
    items = [{**item, "lastHeartbeatEpoch": int(item["lastHeartbeatEpoch"]),
              "expiresInSeconds": max(0, ttl() - (current - int(item["lastHeartbeatEpoch"])))}
             for item in result.items]
    return {"items": items, "nextCursor": result.next_cursor}
