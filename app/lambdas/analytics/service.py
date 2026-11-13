"""Estadísticas mensuales del comercio con Cache-Aside en Redis.

DynamoDB (STORE#id / STATS#YYYY-MM) es la fuente de verdad; Redis guarda una copia con
TTL. Tras confirmar una entrega se invalida la clave. Si Redis falla, se lee DynamoDB.
"""
import json
import logging
import os

from redis.exceptions import RedisError

from lambdas.analytics.repository import AnalyticsRepository
from lambdas.identity.contracts import ActorContext, authorize
from lambdas.shared.exceptions import ValidationError
from lambdas.shared.storage import keys

logger = logging.getLogger(__name__)


def cache_key(store_id, month):
    return f"cache:store:{keys.identifier(store_id)}:stats:{keys.month(month)}"


def invalidate_month(cache, store_id, month):
    try:
        cache.delete(cache_key(store_id, month))
    except RedisError:
        logger.warning("No se pudo invalidar la caché de estadísticas; expirará por TTL")


def get_month_stats(adapter, cache, actor: ActorContext, month):
    """Devuelve el agregado y si salió de caché (`source`: cache | dynamodb)."""
    authorize(actor, "STORE")
    try:
        key = cache_key(actor.store_id, month)
    except ValueError as exc:
        raise ValidationError("month debe tener formato YYYY-MM") from exc
    if cache is not None:
        try:
            cached = cache.get(key)
            if cached is not None:
                return {**json.loads(cached), "source": "cache"}
        except (RedisError, ValueError):
            logger.warning("Caché de estadísticas no disponible; se consulta DynamoDB")
    item = AnalyticsRepository(adapter).get_month(actor.store_id, month)
    stats = {"storeId": actor.store_id, "month": month,
             "deliveredCount": item["deliveredCount"] if item else 0,
             "totalFeeMinor": item["totalFeeMinor"] if item else 0,
             "updatedAt": item["updatedAt"] if item else None}
    if cache is not None:
        try:
            cache.setex(key, int(os.getenv("REDIS_TTL", "300")), json.dumps(stats))
        except RedisError:
            logger.warning("No se pudo guardar la caché de estadísticas")
    return {**stats, "source": "dynamodb"}
