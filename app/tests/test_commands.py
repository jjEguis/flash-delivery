"""SPEC-02: transacciones, estados e idempotencia de los comandos (moto/fakeredis)."""
import pytest
from redis.exceptions import RedisError

from lambdas.analytics.repository import AnalyticsRepository
from lambdas.analytics.service import cache_key, get_month_stats
from lambdas.couriers.repository import CouriersRepository, courier_profile
from lambdas.dispatch import service as dispatch
from lambdas.identity.contracts import ActorContext
from lambdas.orders import service as orders
from lambdas.orders.repository import OrdersRepository
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.stores.repository import StoresRepository, store_profile
from lambdas.tracking.repository import TrackingRepository

ZONE = "centro"
STORE = ActorContext("tienda1", "STORE")
ADMIN = ActorContext("admin", "ADMIN")


def courier(n):
    return ActorContext(f"rep{n}", "COURIER")


@pytest.fixture
def adapter(tabla_dynamodb):
    adapter = DynamoDBAdapter(client=tabla_dynamodb)
    now = clock.now()
    stores = StoresRepository(adapter)
    adapter.transact_write_items([
        stores.build_put(store_profile(store_id="tienda1", owner_id="tienda1", zone_id=ZONE,
                                       name="Tienda 1", enabled=True, created_at=now)),
        stores.build_put(store_profile(store_id="tienda2", owner_id="tienda2", zone_id=ZONE,
                                       name="Tienda 2", enabled=True, created_at=now)),
        stores.build_put(store_profile(store_id="apagada", owner_id="apagada", zone_id=ZONE,
                                       name="Deshabilitada", enabled=False, created_at=now)),
    ])
    add_couriers(adapter, range(1, 4))
    return adapter


def add_couriers(adapter, numbers, *, zone=ZONE, enabled=True, available=True):
    repo, now = CouriersRepository(adapter), clock.now()
    actions = [repo.build_put(courier_profile(courier_id=f"rep{n}", owner_id=f"rep{n}", zone_id=zone,
                                              name=f"Repartidor {n}", enabled=enabled,
                                              available=available, created_at=now)) for n in numbers]
    for start in range(0, len(actions), 100):
        adapter.transact_write_items(actions[start:start + 100])


def create(adapter, key="k1", **overrides):
    data = dict(pickup_address="Calle 1 # 2-3", dropoff_address="Carrera 4 # 5-6", fee_minor=8000)
    data.update(overrides)
    return orders.create_order(adapter, STORE, request_id=key, **data)


def test_create_order_writes_meta_event_view_and_is_idempotent(adapter):
    created = create(adapter)
    repo = OrdersRepository(adapter)
    meta = repo.get_order(created["orderId"])
    assert meta["status"] == "PENDING" and meta["zoneId"] == ZONE and "GSI2PK" in meta
    assert [e["eventType"] for e in repo.list_events(created["orderId"]).items] == ["CREATED"]
    assert repo.list_store_orders_by_status("tienda1", "PENDING").items[0]["orderId"] == created["orderId"]
    assert [o["orderId"] for o in repo.list_open_orders(ZONE).items] == [created["orderId"]]
    assert "trackingTokenHash" not in created and "PK" not in created
    # Reintento con la misma clave: mismo pedido y mismo token, sin segundo pedido.
    again = create(adapter)
    assert again["orderId"] == created["orderId"] and again["trackingToken"] == created["trackingToken"]
    assert len(repo.list_store_orders("tienda1").items) == 1
    with pytest.raises(ConflictError) as error:
        create(adapter, fee_minor=9000)
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    # El token emitido permite el seguimiento público.
    tracking = TrackingRepository(repo).get_tracking(created["trackingToken"])
    assert tracking["status"] == "PENDING"


@pytest.mark.parametrize("actor,kwargs,error,code", [
    (ActorContext("apagada", "STORE"), {}, ForbiddenError, "STORE_NOT_ENABLED"),
    (ActorContext("sin_perfil", "STORE"), {}, NotFoundError, "STORE_NOT_REGISTERED"),
    (ActorContext("rep1", "COURIER"), {}, ForbiddenError, "FORBIDDEN"),
    (STORE, {"fee_minor": 0}, ValidationError, "INVALID_INPUT"),
    (STORE, {"pickup_address": " "}, ValidationError, "INVALID_INPUT"),
    (STORE, {"request_id": "bad#key"}, ValidationError, "INVALID_INPUT"),
])
def test_create_order_rejections(adapter, actor, kwargs, error, code):
    data = dict(request_id="k1", pickup_address="A", dropoff_address="B", fee_minor=1000)
    data.update(kwargs)
    with pytest.raises(error) as raised:
        orders.create_order(adapter, actor, **data)
    assert raised.value.code == code


def test_full_lifecycle_counts_stats_once(adapter, redis_fake):
    order_id = create(adapter)["orderId"]
    rep = courier(1)
    assert dispatch.accept_order(adapter, rep, order_id, request_id="a1")["status"] == "ASSIGNED"
    couriers = CouriersRepository(adapter)
    assert couriers.get_active("rep1")["orderId"] == order_id
    assert OrdersRepository(adapter).list_open_orders(ZONE).items == []
    assert dispatch.pick_up_order(adapter, rep, order_id, request_id="p1")["status"] == "PICKED_UP"
    month = clock.month_of(clock.now())
    redis_fake.set(cache_key("tienda1", month), '{"stale": true}')
    delivered = dispatch.deliver_order(adapter, rep, order_id, request_id="d1", cache=redis_fake)
    assert delivered["status"] == "DELIVERED"
    assert redis_fake.get(cache_key("tienda1", month)) is None  # invalidada tras el commit
    assert couriers.get_active("rep1") is None
    repo = OrdersRepository(adapter)
    assert [e["eventType"] for e in repo.list_events(order_id).items] == ["CREATED", "ASSIGNED", "PICKED_UP", "DELIVERED"]
    assert repo.list_store_orders_by_status("tienda1", "DELIVERED").items[0]["version"] == 4
    assert couriers.list_orders("rep1").items[0]["status"] == "DELIVERED"
    # Reintento idéntico: mismo resultado, sin segunda suma.
    dispatch.deliver_order(adapter, rep, order_id, request_id="d1")
    with pytest.raises(ConflictError) as error:
        dispatch.deliver_order(adapter, rep, order_id, request_id="d2")
    assert error.value.code == "INVALID_TRANSITION"
    stats = AnalyticsRepository(adapter).get_month("tienda1", month)
    assert (stats["deliveredCount"], stats["totalFeeMinor"]) == (1, 8000)
    first = get_month_stats(adapter, redis_fake, STORE, month)
    second = get_month_stats(adapter, redis_fake, STORE, month)
    assert (first["source"], second["source"]) == ("dynamodb", "cache")
    assert second["deliveredCount"] == 1


def test_one_hundred_couriers_compete_one_winner(adapter):
    add_couriers(adapter, range(4, 101))
    order_id = create(adapter)["orderId"]
    winners, codes = [], set()
    for n in range(1, 101):
        try:
            dispatch.accept_order(adapter, courier(n), order_id, request_id=f"acc{n}")
            winners.append(n)
        except ConflictError as error:
            codes.add(error.code)
    assert len(winners) == 1 and codes == {"ORDER_ALREADY_ASSIGNED"}
    assert OrdersRepository(adapter).get_order(order_id)["courierId"] == f"rep{winners[0]}"


def test_courier_cannot_hold_two_active_orders(adapter):
    first = create(adapter, key="k1")["orderId"]
    second = create(adapter, key="k2")["orderId"]
    dispatch.accept_order(adapter, courier(1), first, request_id="a1")
    with pytest.raises(ConflictError) as error:
        dispatch.accept_order(adapter, courier(1), second, request_id="a2")
    assert error.value.code == "COURIER_HAS_ACTIVE_ORDER"
    assert OrdersRepository(adapter).get_order(second)["status"] == "PENDING"


def test_lost_race_at_commit_leaves_no_partial_writes(adapter):
    order_id = create(adapter)["orderId"]
    original = adapter.transact_write_items
    state = {"raced": False}

    def racing(items, **kwargs):
        # Justo antes del commit de rep1, rep2 acepta el mismo pedido.
        if not state["raced"]:
            state["raced"] = True
            adapter.transact_write_items = original
            dispatch.accept_order(adapter, courier(2), order_id, request_id="winner")
        return original(items, **kwargs)

    adapter.transact_write_items = racing
    with pytest.raises(ConflictError) as error:
        dispatch.accept_order(adapter, courier(1), order_id, request_id="loser")
    assert error.value.code == "ORDER_ALREADY_ASSIGNED"
    couriers = CouriersRepository(adapter)
    assert couriers.get_active("rep1") is None
    assert couriers.list_orders("rep1").items == []
    assert couriers.get_active("rep2")["orderId"] == order_id
    events = [e["eventType"] for e in OrdersRepository(adapter).list_events(order_id).items]
    assert events == ["CREATED", "ASSIGNED"]


def test_cancel_rules_and_release(adapter):
    pending = create(adapter, key="k1")["orderId"]
    assert dispatch.cancel_order(adapter, STORE, pending, request_id="c1")["status"] == "CANCELLED"
    with pytest.raises(ConflictError) as error:
        dispatch.accept_order(adapter, courier(1), pending, request_id="a1")
    assert error.value.code == "ORDER_ALREADY_ASSIGNED"
    assigned = create(adapter, key="k2")["orderId"]
    dispatch.accept_order(adapter, courier(1), assigned, request_id="a2")
    with pytest.raises(NotFoundError):
        dispatch.cancel_order(adapter, ActorContext("tienda2", "STORE"), assigned, request_id="x")
    dispatch.cancel_order(adapter, STORE, assigned, request_id="c2")
    assert CouriersRepository(adapter).get_active("rep1") is None
    assert CouriersRepository(adapter).list_orders("rep1").items[0]["status"] == "CANCELLED"
    third = create(adapter, key="k3")["orderId"]
    dispatch.accept_order(adapter, courier(1), third, request_id="a3")  # quedó libre
    dispatch.pick_up_order(adapter, courier(1), third, request_id="p3")
    with pytest.raises(ConflictError) as error:
        dispatch.cancel_order(adapter, STORE, third, request_id="c3")
    assert error.value.code == "INVALID_TRANSITION"


def test_only_assigned_courier_moves_order_and_admin_fails_it(adapter):
    order_id = create(adapter)["orderId"]
    dispatch.accept_order(adapter, courier(1), order_id, request_id="a1")
    with pytest.raises(NotFoundError):
        dispatch.pick_up_order(adapter, courier(2), order_id, request_id="p1")
    with pytest.raises(ConflictError):
        dispatch.deliver_order(adapter, courier(1), order_id, request_id="d1")  # aún no recogido
    dispatch.pick_up_order(adapter, courier(1), order_id, request_id="p1")
    with pytest.raises(ForbiddenError):
        dispatch.fail_order(adapter, STORE, order_id, request_id="f1")
    assert dispatch.fail_order(adapter, ADMIN, order_id, request_id="f1")["status"] == "FAILED"
    assert CouriersRepository(adapter).get_active("rep1") is None


@pytest.mark.parametrize("setup,code", [
    (dict(enabled=False), "COURIER_NOT_ENABLED"),
    (dict(available=False), "COURIER_NOT_AVAILABLE"),
    (dict(zone="norte"), "ZONE_MISMATCH"),
])
def test_courier_eligibility(adapter, setup, code):
    add_couriers(adapter, [50], **setup)
    order_id = create(adapter)["orderId"]
    with pytest.raises((ConflictError, ForbiddenError)) as error:
        dispatch.accept_order(adapter, courier(50), order_id, request_id="a1")
    assert error.value.code == code


def test_order_visibility(adapter):
    order_id = create(adapter)["orderId"]
    assert orders.get_order(adapter, STORE, order_id)["dropoffAddress"]
    for outsider in (ActorContext("tienda2", "STORE"), courier(1)):
        with pytest.raises(NotFoundError):
            orders.get_order(adapter, outsider, order_id)
    dispatch.accept_order(adapter, courier(1), order_id, request_id="a1")
    assert orders.get_order(adapter, courier(1), order_id)["courierId"] == "rep1"
    assert orders.get_order(adapter, ADMIN, order_id)["status"] == "ASSIGNED"


def test_redis_failure_never_reverts_a_committed_delivery(adapter):
    class BrokenRedis:
        def delete(self, *args):
            raise RedisError("caída")

    order_id = create(adapter)["orderId"]
    dispatch.accept_order(adapter, courier(1), order_id, request_id="a1")
    dispatch.pick_up_order(adapter, courier(1), order_id, request_id="p1")
    result = dispatch.deliver_order(adapter, courier(1), order_id, request_id="d1", cache=BrokenRedis())
    assert result["status"] == "DELIVERED"
    assert AnalyticsRepository(adapter).get_month("tienda1", clock.month_of(clock.now()))["deliveredCount"] == 1
