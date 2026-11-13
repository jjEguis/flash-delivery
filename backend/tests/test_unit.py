import json
import pytest
from backend.health import handler
from backend.shared.config.settings import validate_endpoint, Settings


def test_health_contract():
    response = handler({}, None)
    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == {"service": "flashdelivery", "status": "ok", "environment": "local"}


@pytest.mark.parametrize("endpoint", ["https://dynamodb.us-east-1.amazonaws.com", "http://example.com:4566", "http://localhost:4566@evil.com:4566", "http://localhost:4566/path", "http://localhost"])
def test_reject_remote_endpoint(endpoint):
    with pytest.raises(ValueError):
        validate_endpoint(endpoint)


def test_reject_real_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA_REAL")
    with pytest.raises(ValueError):
        Settings.load()


def test_accept_ministack_runtime_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "000000000000")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    assert Settings.load().endpoint.startswith("http://")


@pytest.mark.parametrize("failed_dependency", ["dynamodb", "redis"])
def test_readiness_reports_unavailable_dependency(monkeypatch, failed_dependency):
    from backend import readiness

    class Dependency:
        def __init__(self, name):
            self.name = name
            self.closed = False

        def check(self, **kwargs):
            if self.name == failed_dependency:
                raise ConnectionError("dependency unavailable")
            return True

        describe_table = check
        ping = check

        def close(self):
            self.closed = True

    database, cache = Dependency("dynamodb"), Dependency("redis")
    monkeypatch.setattr(readiness, "aws_client", lambda *args: database)
    monkeypatch.setattr(readiness, "redis_client", lambda *args: cache)
    response = readiness.handler({}, None)
    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert body["checks"][failed_dependency] == "unavailable"
    assert list(body["checks"].values()).count("ok") == 1
    assert database.closed and cache.closed
