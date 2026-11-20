"""Perfiles, guard ACTIVE e historial del repartidor."""
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import Repository


def courier_profile(*, courier_id, owner_id, zone_id, name, enabled, available, created_at,
                    updated_at=None, version=1):
    return make_item("COURIER", courierId=courier_id, ownerId=owner_id, zoneId=zone_id,
                     name=name, enabled=enabled, available=available, createdAt=created_at,
                     updatedAt=updated_at or created_at, version=version)


def active_assignment(courier_id, order_id, assigned_at, version=1):
    return make_item("ACTIVE_ASSIGNMENT", courierId=courier_id, orderId=order_id,
                     assignedAt=assigned_at, version=version)


def courier_order_view(order):
    return make_item("COURIER_ORDER_VIEW", **{name: order[name] for name in
                     ("courierId", "orderId", "storeId", "status", "createdAt", "updatedAt", "version")})


class CouriersRepository(Repository):
    entity_types = {"COURIER", "ACTIVE_ASSIGNMENT", "COURIER_ORDER_VIEW"}

    def get_profile(self, courier_id):
        return self.get(keys.profile(keys.courier(courier_id)))

    def get_active(self, courier_id):
        return self.get(keys.active(courier_id))

    def list_orders(self, courier_id, **page):
        return self.query(keys.courier(courier_id), "ORDER#", index="GSI1", descending=True, **page)

    def build_eligible_condition(self, courier_id, zone_id, version):
        keys.identifier(zone_id)
        return self.build_condition(keys.profile(keys.courier(courier_id)),
                                    "#enabled = :yes AND #available = :yes AND #zone = :zone AND #v = :v",
                                    {"#enabled": "enabled", "#available": "available", "#zone": "zoneId", "#v": "version"},
                                    {":yes": True, ":zone": zone_id, ":v": version})

    def build_release_active(self, courier_id, order_id):
        keys.identifier(order_id)
        return {"Delete": {"TableName": self.adapter.settings.table_name,
                           "Key": {"PK": {"S": keys.courier(courier_id)}, "SK": {"S": "ACTIVE"}},
                           "ConditionExpression": "#order = :order",
                           "ExpressionAttributeNames": {"#order": "orderId"},
                           "ExpressionAttributeValues": {":order": {"S": order_id}}}}
