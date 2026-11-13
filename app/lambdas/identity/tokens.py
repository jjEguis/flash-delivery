"""Tokens de desarrollo firmados con HMAC-SHA256 (formato `payload.firma`, base64url).

Adaptador de identidad LOCAL (ADR-007): no apto para producción. La firma impide que un
cliente cambie su rol o su ID; la clave sale de DEV_AUTH_SECRET y solo se acepta con
ENVIRONMENT=local, que Settings ya exige.
"""
import base64
import hashlib
import hmac
import json
import os
import time

from lambdas.identity.contracts import ActorContext
from lambdas.shared.exceptions import UnauthorizedError, ValidationError

LOCAL_DEFAULT_SECRET = "flashdelivery-local-dev-auth"
TTL_SECONDS = 12 * 3600


def _secret():
    return os.getenv("DEV_AUTH_SECRET", LOCAL_DEFAULT_SECRET).encode("utf-8")


def _b64(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def issue(actor: ActorContext, *, now=None, ttl=TTL_SECONDS):
    issued = int(time.time() if now is None else now)
    payload = {"v": 1, "sub": actor.actor_id, "role": actor.role, "iat": issued, "exp": issued + ttl}
    body = _b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}", payload["exp"]


def verify(token, *, now=None):
    """Devuelve el ActorContext de un token válido o lanza UnauthorizedError."""
    if not isinstance(token, str) or len(token) > 2048 or token.count(".") != 1:
        raise UnauthorizedError("Token inválido")
    body, signature = token.split(".")
    expected = _b64(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise UnauthorizedError("Token inválido")
    try:
        payload = json.loads(_unb64(body))
        if payload.get("v") != 1 or type(payload.get("exp")) is not int:
            raise ValueError
        actor = ActorContext(payload["sub"], payload["role"])
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise UnauthorizedError("Token inválido") from exc
    if payload["exp"] <= int(time.time() if now is None else now):
        raise UnauthorizedError("La sesión expiró; vuelve a iniciar sesión", "TOKEN_EXPIRED")
    return actor
