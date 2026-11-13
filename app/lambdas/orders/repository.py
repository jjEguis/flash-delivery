"""Pedido oficial, eventos y proyecciones consultables sin Scan."""
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import Repository


def order_meta(*, order_id, store_id, zone_id, created_at, pickup_address, dropoff_address,
               fee_minor, currency, tracking_token_hash, status="PENDING", courier_id=None,
               updated_at=None, version=1):
    fields = dict(orderId=order_id, storeId=store_id, zoneId=zone_id, createdAt=created_at,
                  updatedAt=updated_at or created_at, pickupAddress=pickup_address,
                  dropoffAddress=dropoff_address, feeMinor=fee_minor, currency=currency,
                  trackingTokenHash=tracking_token_hash, status=status, version=version)
    if courier_id is not None:
        fields["courierId"] = courier_id
    return make_item("ORDER", **fields)


def order_event(order_id, event_id, event_type, occurred_at):
    return make_item("ORDER_EVENT", orderId=order_id, eventId=event_id,
                     eventType=event_type, occurredAt=occurred_at)


def store_status_view(order):
    return make_item("STORE_STATUS_VIEW", **{name: order[name] for name in
                     ("storeId", "orderId", "status", "createdAt", "updatedAt", "version")})


class OrdersRepository(Repository):
    entity_types = {"ORDER", "ORDER_EVENT", "STORE_STATUS_VIEW"}

    def get_order(self, order_id):
        return self.get(keys.meta(order_id))

    def list_events(self, order_id, **page):
        return self.query(keys.order(order_id), "EVENT#", **page)

    def list_store_orders(self, store_id, **page):
        return self.query(keys.store(store_id), "ORDER#", index="GSI1", descending=True, **page)

    def list_store_orders_by_status(self, store_id, status, **page):
        return self.query(keys.store_state(store_id, status), "CREATED#", index="GSI2", descending=True, **page)

    def list_open_orders(self, zone_id, **page):
        return self.query(keys.zone_open(zone_id), "CREATED#", index="GSI2", **page)
