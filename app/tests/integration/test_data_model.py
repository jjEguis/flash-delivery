"""Modelo de negocio almacenado en MiniStack/Redis reales, con limpieza acotada."""
import hashlib
from datetime import datetime, timedelta
import time
from uuid import uuid4
import pytest
from botocore.exceptions import ClientError

from lambdas.shared.infrastructure.clients import DynamoDBAdapter, redis_client
from lambdas.shared.storage.model import make_item, serialize
from lambdas.shared.storage import keys
from lambdas.stores.repository import StoresRepository
from lambdas.couriers.repository import CouriersRepository, active_assignment, courier_order_view
from lambdas.orders.repository import OrdersRepository, store_status_view, order_event
from lambdas.analytics.repository import AnalyticsRepository
from lambdas.availability.repository import AvailabilityRepository
from lambdas.tracking.repository import TrackingRepository
from scripts.seed_data import seed

pytestmark = pytest.mark.integration


def eventually(check):
    deadline = time.monotonic() + 5
    while not check():
        if time.monotonic() >= deadline:
            raise AssertionError("GSI no reflejó las escrituras en 5 segundos")
        time.sleep(0.1)


def test_AP01_to_AP12_with_real_storage():
    namespace = "SEED_" + uuid4().hex
    adapter, cache = DynamoDBAdapter(), redis_client()
    orders, couriers = OrdersRepository(adapter), CouriersRepository(adapter)
    now = time.time()
    try:
        seed(adapter, cache, namespace, now=now)
        store_id, zone_id = namespace + "_store", namespace + "_zone"
        assert StoresRepository(adapter).get_profile(store_id)["enabled"]
        assert couriers.get_profile(namespace + "_c1")["available"]
        order = orders.get_order(namespace + "_o1")
        assert order["status"] == "PENDING"
        assert len(orders.list_events(namespace + "_o3").items) == 2
        eventually(lambda: len(orders.list_store_orders(store_id).items) == 7)
        eventually(lambda: len(orders.list_store_orders_by_status(store_id, "PENDING").items) == 2)
        eventually(lambda: len(couriers.list_orders(namespace + "_c3").items) == 2)
        eventually(lambda: len(orders.list_open_orders(zone_id).items) == 2)
        first = orders.list_store_orders(store_id, limit=1)
        second = orders.list_store_orders(store_id, limit=1, cursor=first.next_cursor)
        assert first.items[0]["orderId"] != second.items[0]["orderId"]
        assert couriers.get_active(namespace + "_c1")["orderId"] == namespace + "_o3"
        assert len(AvailabilityRepository(cache).list_present(zone_id, now=now).items) == 3
        secret = hashlib.sha256(f"synthetic-only:{namespace}_o3".encode()).hexdigest()
        assert TrackingRepository(orders).get_tracking(f"{namespace}_o3.{secret}")["status"] == "ASSIGNED"
        assert AnalyticsRepository(adapter).get_month(store_id, "2026-01")["deliveredCount"] == 1

        # Sustituir un ítem completo retira automáticamente los atributos del GSI disperso.
        data = {key: value for key, value in order.items() if not key.startswith("GSI")
                and key not in {"PK", "SK", "entityType", "schemaVersion"}}
        data.update(status="ASSIGNED", courierId=namespace + "_c3", version=2)
        data["updatedAt"] = keys.timestamp(datetime.fromisoformat(order["updatedAt"].replace("Z", "+00:00")) + timedelta(seconds=5))
        assigned = make_item("ORDER", **data)
        transaction = [orders.build_put(assigned, expected_version=1),
                       orders.build_put(store_status_view(assigned), expected_version=1),
                       couriers.build_put(courier_order_view(assigned)),
                       couriers.build_put(active_assignment(namespace + "_c3", order["orderId"], assigned["updatedAt"])),
                       orders.build_put(order_event(order["orderId"], "assignment_test", "ASSIGNED", assigned["updatedAt"]))]
        adapter.transact_write_items(transaction)
        assert "GSI2PK" not in orders.get_order(order["orderId"])
        eventually(lambda: len(orders.list_open_orders(zone_id).items) == 1)
        with pytest.raises(ClientError):
            adapter.transact_write_items(transaction)
        assert orders.get_order(order["orderId"])["version"] == 2
    finally:
        # Las proyecciones añadidas no pertenecen al seed original: eliminarlas por clave exacta.
        for key in ({"PK": "COURIER#" + namespace + "_c3", "SK": "ACTIVE"},
                    {"PK": "COURIER#" + namespace + "_c3", "SK": "ORDER#" + namespace + "_o1"}):
            adapter.client.delete_item(TableName=adapter.settings.table_name, Key=serialize(key))
        assigned_event = keys.event(namespace + "_o1", "2026-01-01T00:01:05Z", "assignment_test")
        adapter.client.delete_item(TableName=adapter.settings.table_name, Key=serialize(assigned_event))
        seed(adapter, cache, namespace, clean=True)
        adapter.client.close()
        cache.close()
