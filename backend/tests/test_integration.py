"""No omite fallos de compatibilidad. Solo elimina datos con UUID propios."""
import json
import os
import subprocess
import time
from urllib.request import urlopen
from uuid import uuid4
import pytest
from botocore.exceptions import ClientError
from backend.shared.config.settings import Settings, ROOT, validate_endpoint
from backend.shared.infrastructure.clients import aws_client, redis_client, DynamoDBAdapter

pytestmark = pytest.mark.integration


@pytest.fixture
def settings():
    return Settings.load()


@pytest.fixture
def ddb(settings):
    return DynamoDBAdapter(settings)


@pytest.fixture
def keys(ddb):
    prefix = "TEST#" + uuid4().hex
    values = [{"PK": {"S": prefix}, "SK": {"S": str(i)}} for i in range(3)]
    yield values
    for key in values:
        ddb.client.delete_item(TableName=ddb.settings.table_name, Key=key)


def test_containers_healthy(settings):
    if os.getenv("IN_CDK_DEV") == "1":
        # Sin socket Docker dentro de cdk-dev: comprobar ambos por la red.
        with urlopen(settings.endpoint + "/_ministack/health", timeout=5) as response:
            assert response.status == 200
        client = redis_client(settings)
        try:
            assert client.ping()
        finally:
            client.close()
        return
    result = subprocess.run(["docker", "compose", "ps", "--format", "json"],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    raw = result.stdout.strip()
    rows = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]
    by_service = {row["Service"]: row for row in rows}
    for service in ("ministack", "redis"):
        assert by_service[service]["State"] == "running"
        assert by_service[service]["Health"] == "healthy"


def test_ministack_health(settings):
    with urlopen(settings.endpoint + "/_ministack/health", timeout=settings.read_timeout) as response:
        assert response.status == 200
        assert isinstance(json.load(response), dict)


def test_redis(settings):
    client = redis_client(settings)
    prefix = "flashdelivery:test:" + uuid4().hex
    try:
        assert client.ping()
        client.set(prefix, "ok", ex=30)
        assert client.get(prefix) == "ok"
        assert 0 < client.ttl(prefix) <= 30
        client.sadd(prefix + ":set", "courier")
        assert client.smembers(prefix + ":set") == {"courier"}
        client.zadd(prefix + ":sorted", {"courier": 1})
        assert client.zrange(prefix + ":sorted", 0, -1) == ["courier"]
    finally:
        client.delete(prefix, prefix + ":set", prefix + ":sorted")
        client.close()


def test_table_schema(ddb):
    table = ddb.client.describe_table(TableName=ddb.settings.table_name)["Table"]
    assert table["KeySchema"] == [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}]
    indexes = {index["IndexName"]: index for index in table["GlobalSecondaryIndexes"]}
    assert set(indexes) == {"GSI1", "GSI2"}
    for name, index in indexes.items():
        assert index["KeySchema"] == [{"AttributeName": name+"PK", "KeyType": "HASH"}, {"AttributeName": name+"SK", "KeyType": "RANGE"}]
    assert table["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST"


def test_write_read_update_and_gsi_query(ddb, keys):
    item = {**keys[0], "value": {"S": "initial"}}
    for name in ("GSI1", "GSI2"):
        item[name+"PK"] = keys[0]["PK"]
        item[name+"SK"] = {"S": "indexed"}
    ddb.put_item(Item=item)
    assert ddb.get_item(Key=keys[0], ConsistentRead=True)["Item"] == item
    ddb.update_item(Key=keys[0], UpdateExpression="SET #v = :v",
        ExpressionAttributeNames={"#v": "value"}, ExpressionAttributeValues={":v": {"S": "updated"}})
    assert ddb.get_item(Key=keys[0], ConsistentRead=True)["Item"]["value"] == {"S": "updated"}
    for name in ("GSI1", "GSI2"):
        for _ in range(20):
            result = ddb.query(IndexName=name, KeyConditionExpression="#pk = :pk AND #sk = :sk",
                ExpressionAttributeNames={"#pk": name+"PK", "#sk": name+"SK"},
                ExpressionAttributeValues={":pk": keys[0]["PK"], ":sk": {"S": "indexed"}})
            if result["Items"]:
                break
            time.sleep(0.1)
        assert len(result["Items"]) == 1
        assert result["Items"][0]["PK"] == keys[0]["PK"]


def test_transactions_commit_and_rollback(ddb, keys):
    table = ddb.settings.table_name
    ddb.transact_write_items([{"Put": {"TableName": table, "Item": key}} for key in keys[:2]])
    for key in keys[:2]:
        assert ddb.get_item(Key=key, ConsistentRead=True)["Item"] == key
    with pytest.raises(ClientError) as error:
        ddb.transact_write_items([
            {"Put": {"TableName": table, "Item": keys[2]}},
            {"Put": {"TableName": table, "Item": keys[0], "ConditionExpression": "attribute_not_exists(PK)"}},
        ])
    assert error.value.response["Error"]["Code"] == "TransactionCanceledException"
    assert "Item" not in ddb.get_item(Key=keys[2], ConsistentRead=True)
    assert ddb.get_item(Key=keys[0], ConsistentRead=True)["Item"] == keys[0]


def test_health_through_gateway(settings):
    outputs = json.loads((ROOT / ".local/outputs.json").read_text())
    # Construye la URL desde configuración validada, no confía en una URL arbitraria del disco.
    url = settings.endpoint + "/_aws/execute-api/" + outputs["ApiId"] + "/local/health"
    with urlopen(url, timeout=settings.read_timeout) as response:
        assert response.status == 200
        assert json.load(response) == {"service": "flashdelivery", "status": "ok", "environment": "local"}


@pytest.mark.parametrize("path,checks", [("/api/v1/health", None),
                                       ("/api/v1/ready", {"dynamodb": "ok", "redis": "ok"})])
def test_packaged_lambda_through_gateway(settings, path, checks):
    outputs = json.loads((ROOT / ".local/outputs.json").read_text())
    url = settings.endpoint + "/_aws/execute-api/" + outputs["ApiId"] + "/local" + path
    with urlopen(url, timeout=30) as response:
        body = json.load(response)
        assert response.status == 200
        assert body["status"] == "ok"
        if checks:
            assert body["checks"] == checks
