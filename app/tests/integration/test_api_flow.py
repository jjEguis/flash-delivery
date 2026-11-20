"""Flujo HTTP real: API Gateway → Lambda empaquetada → DynamoDB/Redis en MiniStack."""
import time
from uuid import uuid4

import pytest

from tests.integration.api_client import Api

pytestmark = pytest.mark.integration


@pytest.fixture
def api():
    client = Api()
    yield client
    client.cleanup()


def eventually(fn, attempts=30):
    """Los GSI son eventualmente consistentes: reintentar brevemente."""
    for _ in range(attempts):
        result = fn()
        if result:
            return result
        time.sleep(0.2)
    return fn()


def test_spec04_store_creates_order_visible_to_zone_couriers(api):
    run = uuid4().hex[:8]
    store, other, courier = f"it_s{run}", f"it_x{run}", f"it_c{run}"
    tokens = {name: api.login(name, role) for name, role in ((store, "STORE"), (other, "STORE"), (courier, "COURIER"))}
    admin = api.login("admin", "ADMIN")
    assert api.call("POST", "/api/v1/stores", {"name": "Tienda IT", "zoneId": "centro"}, tokens[store])[0] == 201
    assert api.call("POST", "/api/v1/stores", {"name": "Otra IT", "zoneId": "centro"}, tokens[other])[0] == 201
    assert api.call("POST", "/api/v1/couriers", {"name": "Rep IT", "zoneId": "centro"}, tokens[courier])[0] == 201
    for path in (f"/api/v1/admin/stores/{store}", f"/api/v1/admin/couriers/{courier}"):
        assert api.call("PATCH", path, {"enabled": True}, admin)[0] == 200
    assert api.call("PATCH", "/api/v1/couriers/me/availability", {"available": True}, tokens[courier])[0] == 200

    body = {"pickupAddress": "Calle 1 # 1-1", "dropoffAddress": "Carrera 2 # 2-2", "feeMinor": 6500}
    status, order = api.call("POST", "/api/v1/orders", body, tokens[store], key="it_create")
    api.track(store, "orders.create.v1", "it_create")
    assert status == 201, order
    api.created["orders"].add(order["orderId"])
    # Reintento idempotente por HTTP: mismo pedido, mismo token.
    retry = api.call("POST", "/api/v1/orders", body, tokens[store], key="it_create")[1]
    assert (retry["orderId"], retry["trackingToken"]) == (order["orderId"], order["trackingToken"])

    listed = eventually(lambda: api.call("GET", "/api/v1/stores/me/orders", token=tokens[store])[1]["items"])
    assert [o["orderId"] for o in listed] == [order["orderId"]]
    open_orders = eventually(lambda: [o for o in api.call("GET", "/api/v1/orders/available?zoneId=centro",
                                                          token=tokens[courier])[1]["items"]
                                      if o["orderId"] == order["orderId"]])
    assert open_orders and "dropoffAddress" not in open_orders[0]
    status, events = api.call("GET", f"/api/v1/orders/{order['orderId']}/events", token=tokens[store])
    assert status == 200 and [e["eventType"] for e in events["items"]] == ["CREATED"]
    # Aislamiento: otro comercio no ve el pedido.
    assert api.call("GET", f"/api/v1/orders/{order['orderId']}", token=tokens[other])[0] == 404
    assert api.call("GET", f"/api/v1/orders/{order['orderId']}")[0] == 401


def test_spec05_full_delivery_presence_tracking_and_cache(api):
    run = uuid4().hex[:8]
    store, rep1, rep2 = f"it_s{run}", f"it_a{run}", f"it_b{run}"
    tokens = {name: api.login(name, role) for name, role in ((store, "STORE"), (rep1, "COURIER"), (rep2, "COURIER"))}
    admin = api.login("admin", "ADMIN")
    api.call("POST", "/api/v1/stores", {"name": "Tienda IT", "zoneId": "centro"}, tokens[store])
    api.call("PATCH", f"/api/v1/admin/stores/{store}", {"enabled": True}, admin)
    for rep in (rep1, rep2):
        api.call("POST", "/api/v1/couriers", {"name": rep, "zoneId": "centro"}, tokens[rep])
        api.call("PATCH", f"/api/v1/admin/couriers/{rep}", {"enabled": True}, admin)
        api.call("PATCH", "/api/v1/couriers/me/availability", {"available": True}, tokens[rep])
        status, beat = api.call("POST", "/api/v1/couriers/me/heartbeat", token=tokens[rep])
        assert status == 200 and beat["zoneId"] == "centro", beat
    present = api.call("GET", "/api/v1/zones/centro/couriers?limit=100", token=tokens[store])[1]["items"]
    assert {rep1, rep2} <= {p["courierId"] for p in present}

    status, order = api.call("POST", "/api/v1/orders", {"pickupAddress": "Calle 3", "dropoffAddress": "Calle 9",
                                                        "feeMinor": 4200}, tokens[store], key="it_c")
    assert status == 201, order
    order_id = order["orderId"]
    api.created["orders"].add(order_id)
    api.track(store, "orders.create.v1", "it_c")
    for rep, key in ((rep1, "it_a"), (rep2, "it_b")):
        api.track(rep, "dispatch.accept.v1", key)
    first = api.call("POST", f"/api/v1/orders/{order_id}/accept", token=tokens[rep1], key="it_a")
    second = api.call("POST", f"/api/v1/orders/{order_id}/accept", token=tokens[rep2], key="it_b")
    assert first[0] == 200 and second[0] == 409 and second[1]["error"]["code"] == "ORDER_ALREADY_ASSIGNED"

    month_query = "/api/v1/stores/me/stats"
    miss = api.call("GET", month_query, token=tokens[store])[1]
    hit = api.call("GET", month_query, token=tokens[store])[1]
    assert (miss["source"], hit["source"], hit["deliveredCount"]) == ("dynamodb", "cache", 0)
    for action, key in (("pickup", "it_p"), ("deliver", "it_d")):
        api.track(rep1, f"dispatch.{action}.v1", key)
        status, body = api.call("POST", f"/api/v1/orders/{order_id}/{action}", token=tokens[rep1], key=key)
        assert status == 200, body
    after = api.call("GET", month_query, token=tokens[store])[1]
    assert (after["source"], after["deliveredCount"], after["totalFeeMinor"]) == ("dynamodb", 1, 4200)
    assert api.call("GET", "/api/v1/couriers/me/active", token=tokens[rep1])[1] == {"order": None}

    status, tracked = api.call("GET", f"/api/v1/tracking/{order['trackingToken']}")
    assert status == 200 and tracked["status"] == "DELIVERED"
    assert [e["eventType"] for e in tracked["events"]] == ["CREATED", "ASSIGNED", "PICKED_UP", "DELIVERED"]
    assert "Calle" not in str(tracked) and rep1 not in str(tracked)
    assert api.call("GET", f"/api/v1/tracking/{order_id}.{'A' * 43}")[0] == 404
    assert api.call("DELETE", "/api/v1/couriers/me/heartbeat", token=tokens[rep2])[0] == 204
