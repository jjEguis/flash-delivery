"""SPEC-03: contrato OpenAPI, registro de rutas, identidad local y capa HTTP."""
import importlib
import json
import time

import pytest

from infra.routes import ROUTES
from lambdas.identity import tokens
from lambdas.identity.contracts import ActorContext
from lambdas.shared.config.settings import ROOT
from lambdas.shared.exceptions import UnauthorizedError
from lambdas.shared.http import router

OPENAPI = ROOT.parent / "docs" / "api" / "openapi.json"
PUBLIC = {"POST /api/v1/auth/dev-login", "GET /api/v1/zones", "GET /api/v1/tracking/{token}"}


@pytest.fixture(scope="module")
def spec():
    return json.loads(OPENAPI.read_text(encoding="utf-8"))


def operations(spec):
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            yield f"{method.upper()} {path}", operation


def test_openapi_matches_route_registry(spec):
    documented = {route for route, _ in operations(spec)}
    registered = {route for routes in ROUTES.values() for route in routes}
    assert documented == registered
    assert len(registered) == sum(len(routes) for routes in ROUTES.values())  # sin duplicados


def test_openapi_operations_are_complete(spec):
    raw = json.dumps(spec)
    for ref in {part.split('"')[0] for part in raw.split('"$ref": "')[1:]}:
        node = spec
        for name in ref.lstrip("#/").split("/"):
            node = node[name]  # cada $ref resuelve
    for route, operation in operations(spec):
        assert operation["responses"], route
        assert all(code.isdigit() for code in operation["responses"]), route
        assert (operation.get("security") == []) is (route in PUBLIC), route
        if route.startswith("POST /api/v1/orders"):
            names = [p.get("$ref", "") for p in operation.get("parameters", [])]
            assert "#/components/parameters/IdempotencyKey" in names, route


def test_handlers_implement_exactly_their_registered_routes():
    for module, routes in ROUTES.items():
        try:
            handler = importlib.import_module(f"lambdas.{module}.handler")
        except ModuleNotFoundError:
            continue  # módulo aún no implementado en esta SPEC
        assert list(handler.ROUTES) == routes, module


def test_tokens_sign_expire_and_reject_tampering():
    token, expires = tokens.issue(ActorContext("tienda1", "STORE"), now=1000, ttl=60)
    assert expires == 1060
    assert tokens.verify(token, now=1059) == ActorContext("tienda1", "STORE")
    with pytest.raises(UnauthorizedError) as error:
        tokens.verify(token, now=1060)
    assert error.value.code == "TOKEN_EXPIRED"
    body, signature = token.split(".")
    forged = tokens._b64(json.dumps({"v": 1, "sub": "tienda1", "role": "ADMIN", "iat": 1000, "exp": 9999}).encode())
    for bad in (f"{forged}.{signature}", f"{body}.x{signature[1:]}", "sin-punto", "", None):
        with pytest.raises(UnauthorizedError):
            tokens.verify(bad, now=1000)


def event(method, path, *, body=None, token=None, headers=None):
    all_headers = {"Content-Type": "application/json", **(headers or {})}
    if token:
        all_headers["Authorization"] = f"Bearer {token}"
    return {"version": "2.0", "rawPath": path, "headers": all_headers,
            "requestContext": {"http": {"method": method, "path": path}, "requestId": "req-1"},
            "body": json.dumps(body) if body is not None else None}


def call(main, *args, **kwargs):
    response = main(event(*args, **kwargs), None)
    return response["statusCode"], json.loads(response["body"]) if response["body"] else None


@pytest.fixture
def identity(entorno_test, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    from lambdas.identity import handler
    return importlib.reload(handler).main


def test_dev_login_and_me(identity, monkeypatch):
    status, body = call(identity, "POST", "/api/v1/auth/dev-login", body={"userId": "tienda1", "role": "STORE"})
    assert status == 200 and body["actor"] == {"actorId": "tienda1", "role": "STORE"}
    assert call(identity, "GET", "/api/v1/auth/me", token=body["token"]) == (200, {"actorId": "tienda1", "role": "STORE"})
    # Prefijo de etapa que algunos emuladores dejan en rawPath.
    assert call(identity, "GET", "/local/api/v1/auth/me", token=body["token"])[0] == 200


@pytest.mark.parametrize("payload,status,code", [
    ({"userId": "admin", "role": "ADMIN"}, 403, "INVALID_ADMIN_CODE"),
    ({"userId": "admin", "role": "ADMIN", "adminCode": "otro"}, 403, "INVALID_ADMIN_CODE"),
    ({"userId": "bad#id", "role": "STORE"}, 400, "INVALID_INPUT"),
    ({"userId": "x", "role": "ROOT"}, 400, "INVALID_INPUT"),
])
def test_dev_login_rejections(identity, payload, status, code):
    result_status, body = call(identity, "POST", "/api/v1/auth/dev-login", body=payload)
    assert (result_status, body["error"]["code"]) == (status, code)
    assert body["error"]["requestId"] == "req-1" and body["error"]["message"]


def test_admin_login_with_configured_code(identity, monkeypatch):
    monkeypatch.setenv("DEV_ADMIN_CODE", "codigo-local")
    status, body = call(identity, "POST", "/api/v1/auth/dev-login",
                        body={"userId": "admin", "role": "ADMIN", "adminCode": "codigo-local"})
    assert status == 200 and body["actor"]["role"] == "ADMIN"


def test_error_contract(identity):
    assert call(identity, "GET", "/api/v1/auth/me")[1]["error"]["code"] == "UNAUTHORIZED"
    assert call(identity, "GET", "/api/v1/auth/me", token="a.b")[0] == 401
    assert call(identity, "GET", "/api/v1/nada")[1]["error"]["code"] == "ROUTE_NOT_FOUND"
    bad_json = identity({**event("POST", "/api/v1/auth/dev-login"), "body": "{no-json"}, None)
    assert bad_json["statusCode"] == 400
    assert bad_json["headers"]["X-Request-Id"] == "req-1"


def test_unexpected_errors_are_hidden(entorno_test):
    def boom(request):
        raise RuntimeError("detalle interno con secreto")

    status, body = call(router({"GET /api/v1/boom": boom}), "GET", "/api/v1/boom")
    assert status == 500 and body["error"] == {"code": "INTERNAL_ERROR", "message": "Error interno", "requestId": "req-1"}


def test_rate_limit_per_actor_and_fail_open(entorno_test, monkeypatch, redis_fake):
    from lambdas.shared.infrastructure import clients
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setattr(clients, "shared_redis", lambda: redis_fake)
    main = router({"POST /api/v1/ping": lambda request: (200, {"actor": request.actor.actor_id})})
    token, _ = tokens.issue(ActorContext("rep1", "COURIER"))
    assert [call(main, "POST", "/api/v1/ping", token=token)[0] for _ in range(3)] == [200, 200, 429]
    other, _ = tokens.issue(ActorContext("rep2", "COURIER"))
    assert call(main, "POST", "/api/v1/ping", token=other)[0] == 200

    class Down:
        def incr(self, key):
            raise ConnectionError("redis caído")

    monkeypatch.setattr(clients, "shared_redis", lambda: Down())
    assert call(main, "POST", "/api/v1/ping", token=token)[0] == 200
