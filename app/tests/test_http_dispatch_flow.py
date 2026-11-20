"""SPEC-05: Dispatch, Availability, Tracking y Analytics por HTTP (moto/fakeredis)."""
import json
import time

import pytest

from lambdas.analytics import handler as analytics
from lambdas.availability import handler as availability
from lambdas.availability.repository import heartbeat_key, zone_key
from lambdas.couriers import handler as couriers
from lambdas.dispatch import handler as dispatch
from lambdas.orders import handler as orders
from lambdas.shared import clock
from lambdas.shared.infrastructure import clients
from lambdas.tracking import handler as tracking
from tests.http_helpers import code, invoke
from tests.test_http_base_flow import ADMIN, COURIER, OTHER_STORE, STORE, enabled_courier, enabled_store, new_order

REP2 = ("rep2", "COURIER")


@pytest.fixture
def api(tabla_dynamodb, redis_fake, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    monkeypatch.setitem(clients._SHARED, "adapter", clients.DynamoDBAdapter(client=tabla_dynamodb))
    monkeypatch.setitem(clients._SHARED, "redis", redis_fake)
    enabled_store()
    enabled_courier()
    enabled_courier(REP2)
    return redis_fake


def act(action, order_id, actor, key):
    return invoke(dispatch.main, "POST", f"/api/v1/orders/{order_id}/{action}", actor=actor, key=key)


def test_delivery_lifecycle_tracking_and_cached_stats(api):
    created = new_order()[1]
    order_id, token = created["orderId"], created["trackingToken"]
    assert code(act("accept", order_id, COURIER, None)) == "INVALID_INPUT"  # falta Idempotency-Key
    status, accepted = act("accept", order_id, COURIER, "a1")
    assert status == 200 and accepted["status"] == "ASSIGNED" and accepted["courierId"] == "rep1"
    assert code(act("accept", order_id, REP2, "a2")) == "ORDER_ALREADY_ASSIGNED"
    assert act("accept", order_id, COURIER, "a1")[1]["orderId"] == order_id  # reintento idempotente
    _, active = invoke(couriers.main, "GET", "/api/v1/couriers/me/active", actor=COURIER)
    assert active["order"]["orderId"] == order_id and active["order"]["dropoffAddress"]
    assert invoke(orders.main, "GET", f"/api/v1/orders/{order_id}", actor=COURIER)[0] == 200
    assert code(act("pickup", order_id, REP2, "p1")) == "ORDER_NOT_FOUND"
    assert act("pickup", order_id, COURIER, "p1")[1]["status"] == "PICKED_UP"
    month = clock.month_of(clock.now())
    first = invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=STORE, query={"month": month})[1]
    assert (first["deliveredCount"], first["source"]) == (0, "dynamodb")
    assert invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=STORE, query={"month": month})[1]["source"] == "cache"
    assert act("deliver", order_id, COURIER, "d1")[1]["status"] == "DELIVERED"
    # La entrega invalidó la caché: el siguiente acceso lee DynamoDB con el nuevo total.
    fresh = invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=STORE)[1]
    assert (fresh["deliveredCount"], fresh["totalFeeMinor"], fresh["source"]) == (1, 7000, "dynamodb")
    assert invoke(couriers.main, "GET", "/api/v1/couriers/me/active", actor=COURIER)[1] == {"order": None}
    _, history = invoke(couriers.main, "GET", "/api/v1/couriers/me/orders", actor=COURIER)
    assert history["items"][0]["status"] == "DELIVERED"
    # Seguimiento público: solo estado e hitos, sin direcciones, tarifa ni participantes.
    status, tracked = invoke(tracking.main, "GET", f"/api/v1/tracking/{token}")
    assert status == 200 and set(tracked) == {"orderId", "status", "updatedAt", "events", "nextCursor"}
    assert [e["eventType"] for e in tracked["events"]] == ["CREATED", "ASSIGNED", "PICKED_UP", "DELIVERED"]
    serialized = json.dumps(tracked)
    assert "Carrera" not in serialized and "rep1" not in serialized and "7000" not in serialized
    for bad in (order_id + ".x" * 20, order_id + "." + "A" * 43, "basura"):
        assert code(invoke(tracking.main, "GET", f"/api/v1/tracking/{bad}")) == "TRACKING_NOT_FOUND"
    assert code(invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=STORE, query={"month": "2026-13"})) == "INVALID_INPUT"
    assert code(invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=COURIER)) == "FORBIDDEN"


def test_cancel_and_fail_over_http(api):
    order_id = new_order()[1]["orderId"]
    assert code(act("cancel", order_id, OTHER_STORE, "c1")) in {"ORDER_NOT_FOUND", "FORBIDDEN"}
    assert code(act("cancel", order_id, COURIER, "c1")) == "FORBIDDEN"
    act("accept", order_id, COURIER, "a1")
    assert act("cancel", order_id, STORE, "c1")[1]["status"] == "CANCELLED"
    second = new_order("k2")[1]["orderId"]
    act("accept", second, COURIER, "a2")  # ACTIVE quedó libre tras la cancelación
    act("pickup", second, COURIER, "p2")
    assert code(act("cancel", second, STORE, "c2")) == "INVALID_TRANSITION"
    assert code(act("fail", second, STORE, "f2")) == "FORBIDDEN"
    assert act("fail", second, ADMIN, "f2")[1]["status"] == "FAILED"


def test_presence_heartbeat_listing_and_offline(api):
    status, beat = invoke(availability.main, "POST", "/api/v1/couriers/me/heartbeat", actor=COURIER)
    assert status == 200 and beat["zoneId"] == "centro" and beat["expiresInSeconds"] == 60
    assert 0 < api.ttl(heartbeat_key("rep1")) <= 60
    invoke(availability.main, "POST", "/api/v1/couriers/me/heartbeat", actor=REP2)
    api.zadd(zone_key("centro"), {"fantasma": int(time.time()) - 600})  # miembro vencido
    status, page = invoke(availability.main, "GET", "/api/v1/zones/centro/couriers", actor=STORE)
    assert status == 200 and {p["courierId"] for p in page["items"]} == {"rep1", "rep2"}
    assert code(invoke(availability.main, "GET", "/api/v1/zones/norte/couriers", actor=STORE)) == "ZONE_MISMATCH"
    assert code(invoke(availability.main, "GET", "/api/v1/zones/centro/couriers", actor=COURIER)) == "FORBIDDEN"
    # Salir de la presencia y dejar de estar disponible retiran al repartidor.
    assert invoke(availability.main, "DELETE", "/api/v1/couriers/me/heartbeat", actor=COURIER) == (204, None)
    invoke(couriers.main, "PATCH", "/api/v1/couriers/me/availability", body={"available": False}, actor=REP2)
    assert invoke(availability.main, "GET", "/api/v1/zones/centro/couriers", actor=STORE)[1]["items"] == []
    assert code(invoke(availability.main, "POST", "/api/v1/couriers/me/heartbeat", actor=REP2)) == "COURIER_NOT_AVAILABLE"


def test_redis_down_returns_503_for_presence_but_not_for_dispatch(api, monkeypatch):
    from redis.exceptions import ConnectionError as RedisConnectionError

    class Down:
        def __getattr__(self, name):
            def fail(*args, **kwargs):
                raise RedisConnectionError("redis caído")
            return fail

    monkeypatch.setitem(clients._SHARED, "redis", Down())
    assert code(invoke(availability.main, "POST", "/api/v1/couriers/me/heartbeat", actor=COURIER)) == "DEPENDENCY_UNAVAILABLE"
    order_id = new_order()[1]["orderId"]
    assert act("accept", order_id, COURIER, "a1")[1]["status"] == "ASSIGNED"
    act("pickup", order_id, COURIER, "p1")
    assert act("deliver", order_id, COURIER, "d1")[1]["status"] == "DELIVERED"
    stats = invoke(analytics.main, "GET", "/api/v1/stores/me/stats", actor=STORE)[1]
    assert (stats["deliveredCount"], stats["source"]) == (1, "dynamodb")
