"""Handler empaquetado con moto/fakeredis, incluyendo fallos de dependencia."""
import json
import pytest
from lambdas.readiness import handler


@pytest.fixture
def dependencias(monkeypatch, tabla_dynamodb, redis_fake):
    monkeypatch.setattr(handler, "aws_client", lambda *args: tabla_dynamodb)
    monkeypatch.setattr(handler, "redis_client", lambda *args: redis_fake)
    return tabla_dynamodb, redis_fake


def test_readiness_200(dependencias):
    response = handler.main({}, None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"])["checks"] == {"dynamodb": "ok", "redis": "ok"}


def test_readiness_503_tabla_inexistente(dependencias):
    database, _ = dependencias
    database.delete_table(TableName="test-tabla")
    response = handler.main({}, None)
    assert response["statusCode"] == 503
    assert json.loads(response["body"])["checks"] == {"dynamodb": "unavailable", "redis": "ok"}
