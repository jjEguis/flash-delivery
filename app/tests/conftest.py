"""Fixtures del ejemplo del curso, acotados por prueba; nunca redirigen integraciones."""
import socket

import boto3
import fakeredis
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def sin_red_en_unitarios(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        return

    def reject_network(*args, **kwargs):
        raise AssertionError("Test unitario intentó acceder a la red; usar moto/fakeredis")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket, "getaddrinfo", reject_network)


@pytest.fixture
def entorno_test(monkeypatch):
    # No mutar os.environ al importar conftest: las integraciones necesitan su endpoint.
    for name in ("AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_DYNAMODB"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {
        "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "us-east-1", "AWS_REGION": "us-east-1",
        "AWS_EC2_METADATA_DISABLED": "true", "DYNAMODB_TABLE_NAME": "test-tabla",
        "ENVIRONMENT": "local", "REDIS_HOST": "localhost", "REDIS_PORT": "6379",
        "REDIS_TTL": "300",
    }.items():
        monkeypatch.setenv(name, value)


@pytest.fixture
def tabla_dynamodb(entorno_test, monkeypatch):
    with mock_aws():
        # Moto instala FOOBARKEY/FOOBARSECRET al arrancar; mantener las dummy
        # aceptadas por Settings sin relajar la validación de la aplicación.
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        client = boto3.client("dynamodb", region_name="us-east-1",
                              aws_access_key_id="test", aws_secret_access_key="test")
        client.create_table(
            TableName="test-tabla",
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                       {"AttributeName": "SK", "KeyType": "RANGE"}],
            AttributeDefinitions=[{"AttributeName": name, "AttributeType": "S"}
                                  for name in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")],
            GlobalSecondaryIndexes=[{
                "IndexName": name,
                "KeySchema": [{"AttributeName": name + "PK", "KeyType": "HASH"},
                              {"AttributeName": name + "SK", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"},
            } for name in ("GSI1", "GSI2")],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client
        client.close()


@pytest.fixture
def redis_fake():
    client = fakeredis.FakeRedis(decode_responses=True)
    yield client
    client.close()
