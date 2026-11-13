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
