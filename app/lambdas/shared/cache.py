"""Primitivas Cache-Aside equivalentes al ejemplo; aún sin política de negocio."""
import json
import logging
import os

from redis.exceptions import RedisError
from lambdas.shared.infrastructure.clients import redis_client

logger = logging.getLogger(__name__)


def _get_client():
    return redis_client()


def cache_get(key):
    client = None
    try:
        client = _get_client()
        value = client.get(key)
        return json.loads(value) if value is not None else None
    except (RedisError, json.JSONDecodeError):
        logger.warning("Caché no disponible o inválida; continuar con fuente de verdad")
        return None
    finally:
        if client is not None:
            client.close()


def cache_set(key, value, ttl=None):
    if ttl is None:
        ttl = int(os.getenv("REDIS_TTL", "300"))
    client = None
    try:
        client = _get_client()
        return bool(client.setex(key, ttl, json.dumps(value)))
    except RedisError:
        logger.warning("No se pudo actualizar la caché")
        return False
    finally:
        if client is not None:
            client.close()


def cache_delete(key):
    client = None
    try:
        client = _get_client()
        client.delete(key)
        return True
    except RedisError:
        logger.warning("No se pudo invalidar la caché")
        return False
    finally:
        if client is not None:
            client.close()
