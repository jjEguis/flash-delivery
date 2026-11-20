"""SPEC-02 sobre MiniStack: carreras reales con hilos. Solo borra sus propias claves."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from lambdas.couriers.repository import CouriersRepository, courier_profile
from lambdas.dispatch import service as dispatch
from lambdas.identity.contracts import ActorContext
from lambdas.orders import service as orders
from lambdas.orders.repository import OrdersRepository
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError
from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import serialize
from lambdas.stores.repository import StoresRepository, store_profile

pytestmark = pytest.mark.integration
COURIERS = 100


@pytest.fixture
def world():
    adapter = DynamoDBAdapter()
    run = uuid4().hex[:10]
    zone, store_id = f"z{run}", f"s{run}"
    couriers = [f"c{run}_{n}" for n in range(COURIERS)]
    now = clock.now()
    adapter.transact_write_items([StoresRepository(adapter).build_put(store_profile(
        store_id=store_id, owner_id=store_id, zone_id=zone, name="Tienda IT", enabled=True, created_at=now))])
    repo = CouriersRepository(adapter)
    actions = [repo.build_put(courier_profile(courier_id=c, owner_id=c, zone_id=zone, name=c, enabled=True,
                                              available=True, created_at=now)) for c in couriers]
    for start in range(0, len(actions), 100):
        adapter.transact_write_items(actions[start:start + 100])
    created, requests = [], []
    yield {"adapter": adapter, "store": ActorContext(store_id, "STORE"), "couriers": couriers,
           "orders": created, "requests": requests}
    # Limpieza por claves exactas, sin Scan.
    doomed = [keys.profile(keys.store(store_id))]
    for c in couriers:
        doomed += [keys.profile(keys.courier(c)), keys.active(c)]
    order_repo = OrdersRepository(adapter)
    for order_id in created:
        doomed += [keys.meta(order_id), keys.store_view(store_id, order_id)]
        doomed += [{"PK": e["PK"], "SK": e["SK"]} for e in order_repo.list_events(order_id, limit=100).items]
        doomed += [keys.courier_view(c, order_id) for c in couriers]
    doomed += [keys.request(keys.request_scope(actor, op), request_id) for actor, op, request_id in requests]
    for key in doomed:
        adapter.client.delete_item(TableName=adapter.settings.table_name, Key=serialize(key))


def _create(world, request_id):
    order = orders.create_order(world["adapter"], world["store"], request_id=request_id,
                                pickup_address="Origen IT", dropoff_address="Destino IT", fee_minor=5000)
    world["orders"].append(order["orderId"])
    world["requests"].append((world["store"].actor_id, "orders.create.v1", request_id))
    return order["orderId"]


def _accept(world, courier_id, order_id, request_id):
    world["requests"].append((courier_id, "dispatch.accept.v1", request_id))
    try:
        # Un cliente por hilo: boto3 no comparte sesiones entre hilos de forma segura.
        dispatch.accept_order(DynamoDBAdapter(), ActorContext(courier_id, "COURIER"), order_id,
                              request_id=request_id)
        return "won"
    except ConflictError as error:
        return error.code


def test_one_hundred_concurrent_acceptances_have_one_winner(world):
    order_id = _create(world, "it_create")
    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(lambda c: _accept(world, c, order_id, "it_accept"), world["couriers"]))
    assert results.count("won") == 1, results
    assert set(results) - {"won"} <= {"ORDER_ALREADY_ASSIGNED", "CONCURRENT_UPDATE"}
    winner = world["couriers"][results.index("won")]
    adapter = world["adapter"]
    order = OrdersRepository(adapter).get_order(order_id)
    assert order["status"] == "ASSIGNED" and order["courierId"] == winner
    couriers = CouriersRepository(adapter)
    actives = [c for c in world["couriers"] if couriers.get_active(c)]
    assert actives == [winner]
    events = [e["eventType"] for e in OrdersRepository(adapter).list_events(order_id).items]
    assert events == ["CREATED", "ASSIGNED"]


def test_one_courier_racing_for_two_orders_gets_at_most_one(world):
    first, second = _create(world, "it_create_1"), _create(world, "it_create_2")
    courier_id = world["couriers"][0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: _accept(world, courier_id, pair[0], pair[1]),
                                [(first, "it_a1"), (second, "it_a2")]))
    assert results.count("won") == 1, results
    statuses = sorted(OrdersRepository(world["adapter"]).get_order(o)["status"] for o in (first, second))
    assert statuses == ["ASSIGNED", "PENDING"]
