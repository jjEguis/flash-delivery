from copy import deepcopy
import pytest
from scripts.seed_data import synthetic_items
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import validate, validate_key, make_item, serialize, deserialize
from lambdas.shared.storage.repository import Repository


def test_catalog_types_keys_and_roundtrip():
    items = synthetic_items()
    assert len({(item["PK"], item["SK"]) for item in items}) == len(items)
    assert {item["entityType"] for item in items} == {"STORE", "COURIER", "ORDER", "ORDER_EVENT", "ACTIVE_ASSIGNMENT",
                                                       "STORE_STATUS_VIEW", "COURIER_ORDER_VIEW", "STORE_STATS", "IDEMPOTENCY"}
    for item in items:
        assert validate(deserialize(serialize(item))) == item
        if item["entityType"] == "ORDER":
            assert ("GSI2PK" in item) is (item["status"] == "PENDING")


def test_fixed_utc_timestamp_and_reserved_ids():
    assert keys.timestamp("2026-01-01T00:00:00-05:00") == "2026-01-01T05:00:00.000000Z"
    assert keys.timestamp("2026-01-01T05:00:00Z") == keys.timestamp("2026-01-01T00:00:00-05:00")
    for invalid in ("bad#id", "bad.id", "", "a" * 129, "é"):
        with pytest.raises(ValueError):
            keys.identifier(invalid)
    with pytest.raises(ValueError):
        keys.timestamp("2026-01-01T00:00:00")
    for invalid in ("2026-13", "2026-1", "0000-01"):
        with pytest.raises(ValueError):
            keys.month(invalid)


@pytest.mark.parametrize("field,value", [("version", True), ("version", 0), ("enabled", "true"),
                                         ("name", ""), ("PK", "STORE#wrong"), ("GSI1PK", "unpaired"),
                                         ("createdAt", "2026-01-01T00:00:00Z")])
def test_invalid_store_schema(field, value):
    item = deepcopy(synthetic_items()[0])
    item[field] = value
    with pytest.raises(ValueError):
        validate(item)


def test_size_key_byte_limits_and_sparse_keys():
    for field, maximum in (("PK", 2048), ("SK", 1024)):
        item = {"PK": "x", "SK": "y", field: "é" * (maximum // 2)}
        validate_key(item)
        item[field] += "x"
        with pytest.raises(ValueError):
            validate_key(item)
    item = deepcopy(synthetic_items()[0])
    item["name"] = "é" * (400 * 1024)
    with pytest.raises(ValueError, match="400 KiB"):
        validate(item)
    pending = next(item for item in synthetic_items() if item["entityType"] == "ORDER")
    del pending["GSI2SK"]
    with pytest.raises(ValueError):
        validate(pending)


@pytest.mark.parametrize("field,value", [("feeMinor", -1), ("feeMinor", 1.1), ("feeMinor", True),
                                         ("trackingTokenHash", "raw-token"), ("status", "OPEN")])
def test_invalid_order_fields(field, value):
    item = deepcopy(next(item for item in synthetic_items() if item["entityType"] == "ORDER"))
    item[field] = value
    with pytest.raises(ValueError):
        validate(item)


def test_pending_cannot_be_assigned_and_assigned_requires_courier():
    item = deepcopy(next(item for item in synthetic_items() if item["entityType"] == "ORDER"))
    item["courierId"] = "c1"
    with pytest.raises(ValueError):
        validate(item)
    del item["courierId"]
    item["status"] = "ASSIGNED"
    with pytest.raises(ValueError):
        validate(item)


def test_transaction_builders_and_limits(tabla_dynamodb):
    from lambdas.shared.infrastructure.clients import DynamoDBAdapter
    adapter = DynamoDBAdapter(client=tabla_dynamodb)
    repo = Repository(adapter)
    item = synthetic_items()[0]
    action = repo.build_put(item)
    with pytest.raises(ValueError, match="mismo ítem"):
        adapter.transact_write_items([action, action])
    with pytest.raises(ValueError):
        adapter.transact_write_items([])
    with pytest.raises(ValueError):
        adapter.transact_write_items([action] * 101)
    with pytest.raises(ValueError):
        repo.build_put(item, expected_version=1)
    with pytest.raises(ValueError):
        repo.build_delete({"PK": item["PK"], "SK": item["SK"]}, expected_version=0)
    with pytest.raises(ValueError):
        repo.query(item["PK"], "PROFILE", limit=101)
    with pytest.raises(ValueError, match="4 MiB"):
        adapter.transact_write_items([{"Put": {"TableName": "test-tabla", "Item": {
            "PK": {"S": "oversized"}, "SK": {"S": "test"}, "padding": {"S": "x" * (4 * 1024 * 1024)}}}}])


def test_numeric_limits_and_module_ownership(tabla_dynamodb):
    from lambdas.stores.repository import StoresRepository
    from lambdas.shared.infrastructure.clients import DynamoDBAdapter
    item = deepcopy(synthetic_items()[0])
    item["version"] = 10 ** 38
    with pytest.raises(ValueError, match="38 dígitos"):
        validate(item)
    order = next(item for item in synthetic_items() if item["entityType"] == "ORDER")
    with pytest.raises(ValueError, match="propietario"):
        StoresRepository(DynamoDBAdapter(client=tabla_dynamodb)).build_put(order)
