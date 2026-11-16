"""Credencial pública con nonce aleatorio, vencimiento y revocación persistente."""
import os
import secrets
import time

from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item, serialize
from lambdas.shared.storage.repository import Repository


def access_key(order_id):
    return {"PK": keys.order(order_id), "SK": "TRACKING"}


def new_access(order_id):
    return make_item("TRACKING_ACCESS", orderId=order_id, nonce=secrets.token_urlsafe(32),
                     expiresAt=int(time.time()) + int(os.getenv("TRACKING_TOKEN_TTL_SECONDS", "86400")),
                     revoked=False)


class TrackingAccess(Repository):
    entity_types = {"TRACKING_ACCESS"}

    def for_order(self, order_id):
        return self.get(access_key(order_id))

    def revoke(self, order_id):
        self.adapter.update_item(Key=serialize(access_key(order_id)),
            UpdateExpression="SET revoked = :yes", ConditionExpression="attribute_exists(PK)",
            ExpressionAttributeValues=serialize({":yes": True}))
