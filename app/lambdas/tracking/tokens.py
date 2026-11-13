"""Emisión del token público de seguimiento.

El secreto se deriva con HMAC de una clave del servidor y el ID del pedido. Así un
reintento idempotente de la creación puede devolver el mismo token sin guardar el
secreto en claro: en DynamoDB solo queda su SHA-256 (trackingTokenHash).
"""
import base64
import hashlib
import hmac
import os

from lambdas.shared.storage import keys
from lambdas.tracking.repository import tracking_token

LOCAL_DEFAULT_KEY = "flashdelivery-local-tracking-key"


def _key():
    return os.getenv("TRACKING_TOKEN_KEY", LOCAL_DEFAULT_KEY).encode("utf-8")


def issue_token(order_id):
    """Devuelve (token público `orderId.secret`, hash SHA-256 del secreto)."""
    digest = hmac.new(_key(), keys.identifier(order_id).encode("utf-8"), hashlib.sha256).digest()
    secret = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return tracking_token(order_id, secret)
