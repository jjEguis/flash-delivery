"""Mismos escenarios de caché del curso, sin Redis real."""
import pytest
from redis.exceptions import ConnectionError
from lambdas.shared import cache


@pytest.fixture(autouse=True)
def parchear_redis(monkeypatch, redis_fake):
    monkeypatch.setattr(cache, "_get_client", lambda: redis_fake)


def test_set_get_y_ttl(redis_fake):
    assert cache.cache_set("test:item", {"id": "x1"}, ttl=60)
    assert cache.cache_get("test:item") == {"id": "x1"}
    assert 1 <= redis_fake.ttl("test:item") <= 60


def test_ttl_de_entorno(monkeypatch, redis_fake):
    monkeypatch.setenv("REDIS_TTL", "120")
    assert cache.cache_set("test:item", {"v": 1})
    assert 1 <= redis_fake.ttl("test:item") <= 120


def test_clave_inexistente():
    assert cache.cache_get("test:missing") is None
    assert cache.cache_delete("test:missing")


def test_delete_invalida():
    cache.cache_set("test:item", {"v": 1})
    assert cache.cache_delete("test:item")
    assert cache.cache_get("test:item") is None


def test_json_corrupto_se_trata_como_miss(redis_fake):
    redis_fake.set("test:item", "invalid json")
    assert cache.cache_get("test:item") is None


@pytest.mark.parametrize("method,args,expected", [
    ("get", ("test:item",), None),
    ("setex", ("test:item", {"v": 1}), False),
    ("delete", ("test:item",), False),
])
def test_redis_caido_no_interrumpe_aplicacion(monkeypatch, redis_fake, method, args, expected):
    def fail(*args, **kwargs):
        raise ConnectionError("sin conexión")

    monkeypatch.setattr(redis_fake, method, fail)
    operation = {"get": cache.cache_get, "setex": cache.cache_set, "delete": cache.cache_delete}[method]
    assert operation(*args) is expected
