"""AP11: token localizable por ID y comprobable por hash; respuesta mínima."""
import hashlib
import hmac
import re
import secrets
from typing import Protocol
from lambdas.shared.storage import keys
from lambdas.shared.storage.repository import Page


class OrderReader(Protocol):
    def get_order(self, order_id): ...
    def list_events(self, order_id, **page) -> Page: ...


def tracking_token(order_id, secret=None):
    secret = secrets.token_urlsafe(32) if secret is None else secret
    if not isinstance(secret, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", secret):
        raise ValueError("Secreto de seguimiento inválido")
    return f"{keys.identifier(order_id)}.{secret}", hashlib.sha256(secret.encode()).hexdigest()


class TrackingRepository:
    def __init__(self, orders: OrderReader):
        self.orders = orders

    def get_tracking(self, token, *, limit=25, cursor=None):
        if not isinstance(token, str) or len(token) > 257 or token.count(".") != 1:
            return None
        order_id, secret = token.split(".")
        try:
            _, digest = tracking_token(order_id, secret)
        except ValueError:
            return None
        order = self.orders.get_order(order_id)
        if not order or not hmac.compare_digest(digest, order["trackingTokenHash"]):
            return None
        events = self.orders.list_events(order_id, limit=limit, cursor=cursor)
        return {"orderId": order_id, "status": order["status"], "updatedAt": order["updatedAt"],
                "events": [{"eventType": event["eventType"], "occurredAt": event["occurredAt"]}
                           for event in events.items], "nextCursor": events.next_cursor}
