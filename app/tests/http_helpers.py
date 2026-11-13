"""Utilidades para invocar handlers con eventos HTTP API v2 en pruebas unitarias."""
import json

from lambdas.identity.contracts import ActorContext
from lambdas.identity.tokens import issue


def token(actor_id, role):
    return issue(ActorContext(actor_id, role))[0]


def invoke(main, method, path, *, body=None, actor=None, key=None, query=None):
    headers = {"content-type": "application/json"}
    if actor:
        headers["authorization"] = "Bearer " + token(*actor)
    if key:
        headers["idempotency-key"] = key
    event = {"version": "2.0", "rawPath": path, "headers": headers, "queryStringParameters": query,
             "requestContext": {"http": {"method": method, "path": path}, "requestId": "test"},
             "body": json.dumps(body) if body is not None else None}
    response = main(event, None)
    return response["statusCode"], (json.loads(response["body"]) if response["body"] else None)


def code(result):
    return result[1]["error"]["code"]
