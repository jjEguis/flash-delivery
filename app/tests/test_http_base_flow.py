"""SPEC-04: endpoints de Stores, Couriers y Orders con moto/fakeredis (sin red)."""
import pytest

from lambdas.couriers import handler as couriers
from lambdas.orders import handler as orders
from lambdas.shared.infrastructure import clients
from lambdas.stores import handler as stores
from tests.http_helpers import code, invoke

STORE = ("tienda1", "STORE")
OTHER_STORE = ("tienda2", "STORE")
COURIER = ("rep1", "COURIER")
ADMIN = ("admin", "ADMIN")


@pytest.fixture
def api(tabla_dynamodb, redis_fake, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setitem(clients._SHARED, "adapter", clients.DynamoDBAdapter(client=tabla_dynamodb))
    monkeypatch.setitem(clients._SHARED, "redis", redis_fake)
    return redis_fake


def enabled_store(actor=STORE, zone="centro"):
    assert invoke(stores.main, "POST", "/api/v1/stores", body={"name": "Tienda", "zoneId": zone}, actor=actor)[0] == 201
    assert invoke(stores.main, "PATCH", f"/api/v1/admin/stores/{actor[0]}", body={"enabled": True}, actor=ADMIN)[0] == 200


def enabled_courier(actor=COURIER, zone="centro"):
    assert invoke(couriers.main, "POST", "/api/v1/couriers", body={"name": "Rep", "zoneId": zone}, actor=actor)[0] == 201
    assert invoke(couriers.main, "PATCH", f"/api/v1/admin/couriers/{actor[0]}", body={"enabled": True}, actor=ADMIN)[0] == 200
    assert invoke(couriers.main, "PATCH", "/api/v1/couriers/me/availability", body={"available": True}, actor=actor)[0] == 200


def new_order(key="k1", actor=STORE, fee=7000):
    return invoke(orders.main, "POST", "/api/v1/orders", actor=actor, key=key,
                  body={"pickupAddress": "Calle 10 # 4-20", "dropoffAddress": "Carrera 7 # 15-3", "feeMinor": fee})


def test_zones_are_public(api):
    status, body = invoke(stores.main, "GET", "/api/v1/zones")
    assert status == 200 and {"zoneId": "centro", "name": "Centro"} in body["items"]


def test_store_profile_lifecycle(api):
    assert code(invoke(stores.main, "GET", "/api/v1/stores/me", actor=STORE)) == "STORE_NOT_REGISTERED"
    assert code(invoke(stores.main, "POST", "/api/v1/stores", body={"name": "X", "zoneId": "marte"}, actor=STORE)) == "INVALID_ZONE"
    status, store = invoke(stores.main, "POST", "/api/v1/stores", body={"name": " Tienda Uno ", "zoneId": "centro"}, actor=STORE)
    assert status == 201 and store == {**store, "storeId": "tienda1", "name": "Tienda Uno", "enabled": False}
    assert code(invoke(stores.main, "POST", "/api/v1/stores", body={"name": "Otra", "zoneId": "centro"}, actor=STORE)) == "STORE_ALREADY_REGISTERED"
    assert code(invoke(stores.main, "PATCH", "/api/v1/admin/stores/tienda1", body={"enabled": True}, actor=STORE)) == "FORBIDDEN"
    assert code(invoke(stores.main, "PATCH", "/api/v1/admin/stores/nadie", body={"enabled": True}, actor=ADMIN)) == "STORE_NOT_FOUND"
    status, enabled = invoke(stores.main, "PATCH", "/api/v1/admin/stores/tienda1", body={"enabled": True}, actor=ADMIN)
    assert status == 200 and enabled["enabled"] is True and enabled["version"] == 2
    assert invoke(stores.main, "GET", "/api/v1/stores/me", actor=COURIER)[0] == 403
    assert invoke(stores.main, "GET", "/api/v1/stores/me")[0] == 401


def test_courier_profile_availability_and_admin(api):
    assert invoke(couriers.main, "POST", "/api/v1/couriers", body={"name": "Rep", "zoneId": "norte"}, actor=COURIER)[0] == 201
    assert code(invoke(couriers.main, "PATCH", "/api/v1/couriers/me/availability",
                       body={"available": True}, actor=COURIER)) == "COURIER_NOT_ENABLED"
    invoke(couriers.main, "PATCH", "/api/v1/admin/couriers/rep1", body={"enabled": True}, actor=ADMIN)
    status, courier = invoke(couriers.main, "PATCH", "/api/v1/couriers/me/availability", body={"available": True}, actor=COURIER)
    assert status == 200 and courier["available"] is True
    assert invoke(couriers.main, "GET", "/api/v1/couriers/me/active", actor=COURIER) == (200, {"order": None})
    # Deshabilitar al repartidor también lo deja no disponible.
    _, disabled = invoke(couriers.main, "PATCH", "/api/v1/admin/couriers/rep1", body={"enabled": False}, actor=ADMIN)
    assert (disabled["enabled"], disabled["available"]) == (False, False)
    assert code(invoke(couriers.main, "PATCH", "/api/v1/couriers/me/availability",
                       body={"available": "si"}, actor=COURIER)) == "INVALID_INPUT"


def test_create_order_over_http(api):
    assert code(invoke(orders.main, "POST", "/api/v1/orders", actor=STORE,
                       body={"pickupAddress": "A", "dropoffAddress": "B", "feeMinor": 1})) == "INVALID_INPUT"
    assert code(new_order()) == "STORE_NOT_REGISTERED"
    invoke(stores.main, "POST", "/api/v1/stores", body={"name": "Tienda", "zoneId": "centro"}, actor=STORE)
    assert code(new_order()) == "STORE_NOT_ENABLED"
    invoke(stores.main, "PATCH", "/api/v1/admin/stores/tienda1", body={"enabled": True}, actor=ADMIN)
    status, created = new_order()
    assert status == 201 and created["status"] == "PENDING" and created["trackingToken"].startswith(created["orderId"] + ".")
    assert new_order()[1]["orderId"] == created["orderId"]  # reintento idempotente
    assert code(new_order(fee=9999)) == "IDEMPOTENCY_CONFLICT"
    assert code(new_order(key="k2", actor=COURIER)) == "FORBIDDEN"


def test_store_lists_and_isolation(api):
    enabled_store()
    enabled_store(OTHER_STORE)
    first = new_order("k1")[1]["orderId"]
    second = new_order("k2")[1]["orderId"]
    status, page = invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE, query={"limit": "1"})
    assert status == 200 and [o["orderId"] for o in page["items"]] == [second] and page["nextCursor"]
    assert "dropoffAddress" not in page["items"][0]
    _, rest = invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE,
                     query={"limit": "1", "cursor": page["nextCursor"]})
    assert [o["orderId"] for o in rest["items"]] == [first]
    _, pending = invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE, query={"status": "PENDING"})
    assert len(pending["items"]) == 2
    assert code(invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE, query={"status": "OPEN"})) == "INVALID_INPUT"
    assert code(invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE, query={"limit": "0"})) == "INVALID_INPUT"
    assert code(invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=STORE, query={"cursor": "manipulado"})) == "INVALID_INPUT"
    # Otro comercio no ve el pedido ni su historial, ni lo encuentra en sus listados.
    assert code(invoke(orders.main, "GET", f"/api/v1/orders/{first}", actor=OTHER_STORE)) == "ORDER_NOT_FOUND"
    assert code(invoke(orders.main, "GET", f"/api/v1/orders/{first}/events", actor=OTHER_STORE)) == "ORDER_NOT_FOUND"
    assert invoke(orders.main, "GET", "/api/v1/stores/me/orders", actor=OTHER_STORE)[1]["items"] == []
    status, detail = invoke(orders.main, "GET", f"/api/v1/orders/{first}", actor=STORE)
    assert status == 200 and detail["dropoffAddress"] == "Carrera 7 # 15-3"
    assert invoke(orders.main, "GET", f"/api/v1/orders/{first}/events", actor=STORE)[1]["items"][0]["eventType"] == "CREATED"


def test_open_orders_for_couriers(api):
    enabled_store()
    order_id = new_order()[1]["orderId"]
    assert code(invoke(orders.main, "GET", "/api/v1/orders/available", actor=COURIER, query={"zoneId": "centro"})) == "COURIER_NOT_REGISTERED"
    enabled_courier()
    status, page = invoke(orders.main, "GET", "/api/v1/orders/available", actor=COURIER, query={"zoneId": "centro"})
    assert status == 200 and [o["orderId"] for o in page["items"]] == [order_id]
    assert "dropoffAddress" not in page["items"][0] and page["items"][0]["pickupAddress"]
    assert code(invoke(orders.main, "GET", "/api/v1/orders/available", actor=COURIER, query={"zoneId": "norte"})) == "ZONE_MISMATCH"
    assert code(invoke(orders.main, "GET", "/api/v1/orders/available", actor=COURIER)) == "INVALID_INPUT"
    assert code(invoke(orders.main, "GET", "/api/v1/orders/available", actor=STORE, query={"zoneId": "centro"})) == "FORBIDDEN"
    # Un repartidor no ve el detalle de un pedido que no tiene asignado.
    assert code(invoke(orders.main, "GET", f"/api/v1/orders/{order_id}", actor=COURIER)) == "ORDER_NOT_FOUND"
