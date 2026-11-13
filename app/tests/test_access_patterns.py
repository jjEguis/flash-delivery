"""AP01–AP12 contra moto/fakeredis, registrando las operaciones y claves reales."""
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import pytest
from botocore.exceptions import ClientError

from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.shared.storage.model import serialize, validate, make_item
from lambdas.shared.storage.repository import Repository
from lambdas.shared.storage.idempotency import IdempotencyRepository
from lambdas.shared.storage import keys
from lambdas.stores.repository import StoresRepository
from lambdas.couriers.repository import CouriersRepository, active_assignment, courier_order_view
from lambdas.orders.repository import OrdersRepository, store_status_view, order_event
from lambdas.analytics.repository import AnalyticsRepository
from lambdas.tracking.repository import TrackingRepository
from lambdas.availability.repository import AvailabilityRepository, heartbeat_key, zone_key
from scripts.seed_data import seed, synthetic_items


class RecordingClient:
    def __init__(self, client):
        self.client, self.calls = client, []

    def __getattr__(self, name):
        if name == "scan":
            raise AssertionError("Scan no está permitido")
        def invoke(**args):
            assert "FilterExpression" not in args
            self.calls.append((name, deepcopy(args)))
            return getattr(self.client, name)(**args)
        return invoke


@pytest.fixture
def dataset(tabla_dynamodb, redis_fake):
    recorder = RecordingClient(tabla_dynamodb)
    adapter = DynamoDBAdapter(client=recorder)
    seed(adapter, redis_fake, now=1000)
    recorder.calls.clear()
    return adapter, recorder, redis_fake


@pytest.mark.parametrize("pattern,repository,method,args,expected", [
    ("AP01", StoresRepository, "get_profile", ("SEED_demo_store",), keys.profile(keys.store("SEED_demo_store"))),
    ("AP02", CouriersRepository, "get_profile", ("SEED_demo_c1",), keys.profile(keys.courier("SEED_demo_c1"))),
    ("AP03", OrdersRepository, "get_order", ("SEED_demo_o1",), keys.meta("SEED_demo_o1")),
    ("AP09", CouriersRepository, "get_active", ("SEED_demo_c1",), keys.active("SEED_demo_c1")),
    ("AP12", AnalyticsRepository, "get_month", ("SEED_demo_store", "2026-01"), keys.stats("SEED_demo_store", "2026-01")),
])
def test_exact_keys_and_strong_reads(dataset, pattern, repository, method, args, expected):
    adapter, recorder, _ = dataset
    result = getattr(repository(adapter), method)(*args)
    assert result is not None
    operation, call = recorder.calls[-1]
    assert operation == "get_item"
    assert call["Key"] == serialize(expected)
    assert call["ConsistentRead"] is True


@pytest.mark.parametrize("pattern,repository,method,args,index,partition,prefix,count,descending", [
    ("AP04", OrdersRepository, "list_events", ("SEED_demo_o3",), None, "ORDER#SEED_demo_o3", "EVENT#", 2, False),
    ("AP05", OrdersRepository, "list_store_orders", ("SEED_demo_store",), "GSI1", "STORE#SEED_demo_store", "ORDER#", 7, True),
    ("AP06", OrdersRepository, "list_store_orders_by_status", ("SEED_demo_store", "PENDING"), "GSI2", "STORE#SEED_demo_store#PENDING", "CREATED#", 2, True),
    ("AP07", CouriersRepository, "list_orders", ("SEED_demo_c3",), "GSI1", "COURIER#SEED_demo_c3", "ORDER#", 2, True),
    ("AP08", OrdersRepository, "list_open_orders", ("SEED_demo_zone",), "GSI2", "ZONE#SEED_demo_zone#OPEN", "CREATED#", 2, False),
])
def test_paginated_queries_without_scan(dataset, pattern, repository, method, args,
                                        index, partition, prefix, count, descending):
    adapter, recorder, _ = dataset
    items, cursor = [], None
    for _ in range(20):
        page = getattr(repository(adapter), method)(*args, limit=1, cursor=cursor)
        items.extend(page.items)
        cursor = page.next_cursor
        if not cursor:
            break
    assert cursor is None
    assert len(items) == count
    assert len({(item["PK"], item["SK"]) for item in items}) == count
    for operation, call in recorder.calls:
        assert operation == "query"
        assert call["KeyConditionExpression"] == "#pk = :pk AND begins_with(#sk, :prefix)"
        assert call["ExpressionAttributeValues"] == serialize({":pk": partition, ":prefix": prefix})
        assert call.get("IndexName") == index
        assert call["ConsistentRead"] is (index is None)
        assert call["ScanIndexForward"] is (not descending)
        assert call["Limit"] == 1


def test_AP10_presence_pagination_and_stale_members(dataset):
    _, _, cache = dataset
    repo = AvailabilityRepository(cache)
    cache.zadd(zone_key("SEED_demo_zone"), {"expired": 999, "old": 900, "other_zone": 999, "corrupt": 999, "bad#courier": 999})
    cache.set(heartbeat_key("corrupt"), "invalid-json", ex=60)
    cache.set(heartbeat_key("old"), json.dumps({"zoneId": "SEED_demo_zone", "lastHeartbeatEpoch": 900}), ex=60)
    cache.set(heartbeat_key("other_zone"), json.dumps({"zoneId": "other", "lastHeartbeatEpoch": 999}), ex=60)
    first = repo.list_present("SEED_demo_zone", now=1000, limit=1)
    second = repo.list_present("SEED_demo_zone", now=1000, limit=1, cursor=first.next_cursor)
    third = repo.list_present("SEED_demo_zone", now=1000, limit=1, cursor=second.next_cursor)
    assert [p.items[0]["courierId"] for p in (first, second, third)] == ["SEED_demo_c1", "SEED_demo_c2", "SEED_demo_c3"]
    assert third.next_cursor is None
    with pytest.raises(ValueError):
        repo.list_present("other", now=1000, cursor=first.next_cursor)
    cache.delete(heartbeat_key("SEED_demo_c1"))
    assert len(repo.list_present("SEED_demo_zone", now=1000).items) == 2
    assert repo.list_present("SEED_demo_zone", now=1061).items == []


def test_AP11_tracking_get_query_and_privacy(dataset):
    adapter, recorder, _ = dataset
    repo = TrackingRepository(OrdersRepository(adapter))
    secret = hashlib.sha256(b"synthetic-only:SEED_demo_o3").hexdigest()
    token = f"SEED_demo_o3.{secret}"
    result = repo.get_tracking(token, limit=1)
    assert result["status"] == "ASSIGNED"
    assert set(result) == {"orderId", "status", "updatedAt", "events", "nextCursor"}
    assert set(result["events"][0]) == {"eventType", "occurredAt"}
    assert [name for name, _ in recorder.calls] == ["get_item", "query"]
    assert recorder.calls[0][1]["Key"] == serialize(keys.meta("SEED_demo_o3"))
    assert recorder.calls[1][1]["ExpressionAttributeValues"][":pk"] == {"S": "ORDER#SEED_demo_o3"}
    final = repo.get_tracking(token, limit=1, cursor=result["nextCursor"])
    assert final["events"][0]["eventType"] == "ASSIGNED"
    recorder.calls.clear()
    assert repo.get_tracking("SEED_demo_o3." + "x" * 32) is None
    assert [name for name, _ in recorder.calls] == ["get_item"]
    assert repo.get_tracking("invalid") is None


def test_date_range_and_cursor_query_binding(dataset):
    adapter, _, _ = dataset
    repo = OrdersRepository(adapter)
    page = repo.list_store_orders("SEED_demo_store", limit=1, start="2026-01-01T00:02:00Z", end="2026-01-01T00:03:00Z")
    assert page.items[0]["orderId"] == "SEED_demo_o3"
    assert repo.list_store_orders("SEED_demo_store", limit=1, cursor=page.next_cursor,
                                  start="2026-01-01T00:02:00Z", end="2026-01-01T00:03:00Z").items[0]["orderId"] == "SEED_demo_o2"
    with pytest.raises(ValueError):
        repo.list_store_orders("other", cursor=page.next_cursor)
    with pytest.raises(ValueError):
        repo.list_store_orders("SEED_demo_store", cursor=page.next_cursor)
    with pytest.raises(ValueError):
        repo.list_events("SEED_demo_o3", cursor="not-a-cursor")
    with pytest.raises(ValueError):
        repo.list_store_orders("SEED_demo_store", start="2026-02-01T00:00:00Z", end="2026-01-01T00:00:00Z")


def test_same_timestamp_uses_id_to_paginate_without_loss(dataset):
    adapter, _, _ = dataset
    repo = OrdersRepository(adapter)
    first = repo.get_order("SEED_demo_o1")
    second = repo.get_order("SEED_demo_o2")
    data = {k: v for k, v in second.items() if k not in {"PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "entityType", "schemaVersion"}}
    data.update(createdAt=first["createdAt"], version=2)
    tied = make_item("ORDER", **data)
    adapter.transact_write_items([repo.build_put(tied, expected_version=1),
                                  repo.build_put(store_status_view(tied), expected_version=1)])
    page = repo.list_open_orders("SEED_demo_zone", start=first["createdAt"], end=first["createdAt"], limit=1)
    next_page = repo.list_open_orders("SEED_demo_zone", start=first["createdAt"], end=first["createdAt"],
                                      limit=1, cursor=page.next_cursor)
    assert [page.items[0]["orderId"], next_page.items[0]["orderId"]] == ["SEED_demo_o1", "SEED_demo_o2"]


def test_projection_replacement_and_atomic_rollback(dataset):
    adapter, _, _ = dataset
    orders, couriers = OrdersRepository(adapter), CouriersRepository(adapter)
    old = orders.get_order("SEED_demo_o1")
    data = {k: v for k, v in old.items() if k not in {"PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "entityType", "schemaVersion"}}
    data.update(status="ASSIGNED", courierId="SEED_demo_c3", version=2)
    data["updatedAt"] = keys.timestamp(datetime.fromisoformat(old["updatedAt"].replace("Z", "+00:00")) + timedelta(seconds=5))
    new = make_item("ORDER", **data)
    actions = [orders.build_put(new, expected_version=1), orders.build_put(store_status_view(new), expected_version=1),
               couriers.build_put(courier_order_view(new)), couriers.build_put(active_assignment("SEED_demo_c3", new["orderId"], new["updatedAt"])),
               orders.build_put(order_event(new["orderId"], "assignment_test", "ASSIGNED", new["updatedAt"]))]
    adapter.transact_write_items(actions)
    current = orders.get_order(old["orderId"])
    assert "GSI2PK" not in current and "GSI2SK" not in current
    assert [item["orderId"] for item in orders.list_open_orders("SEED_demo_zone").items] == ["SEED_demo_o2"]
    assert orders.list_store_orders_by_status("SEED_demo_store", "ASSIGNED").items[0]["status"] == "ASSIGNED"
    assert any(item["orderId"] == old["orderId"] for item in couriers.list_orders("SEED_demo_c3").items)
    with pytest.raises(ClientError):
        adapter.transact_write_items(actions)
    assert orders.get_order(old["orderId"])["version"] == 2


def test_profile_conditions_and_active_release(dataset):
    adapter, _, _ = dataset
    store, courier = StoresRepository(adapter), CouriersRepository(adapter)
    adapter.transact_write_items([store.build_enabled_condition("SEED_demo_store", 1),
                                  courier.build_eligible_condition("SEED_demo_c1", "SEED_demo_zone", 1)])
    with pytest.raises(ClientError):
        adapter.transact_write_items([courier.build_eligible_condition("SEED_demo_c1", "other", 1)])
    with pytest.raises(ClientError):
        adapter.transact_write_items([courier.build_release_active("SEED_demo_c1", "other")])
    adapter.transact_write_items([courier.build_release_active("SEED_demo_c1", "SEED_demo_o3")])
    assert courier.get_active("SEED_demo_c1") is None


def test_idempotency_and_seed_repeat_cleanup(dataset):
    adapter, _, cache = dataset
    scope = keys.request_scope("SEED_demo_owner", "orders.create.v1")
    repo = IdempotencyRepository(adapter)
    assert repo.get_result(scope, "demo_request")["result"] == {"orderId": "SEED_demo_o1"}
    before = synthetic_items()
    assert seed(adapter, cache, now=1000) == len(before)
    assert seed(adapter, cache, clean=True) == len(before)
    for item in before:
        assert Repository(adapter).get({k: item[k] for k in ("PK", "SK")}) is None
    assert cache.zcard(zone_key("SEED_demo_zone")) == 0
