"""Adaptador HTTP compartido para los handlers Lambda (API Gateway HTTP API, evento v2).

Los handlers solo validan HTTP, obtienen la identidad, invocan un caso de uso y traducen
errores. Aquí viven el enrutado por plantilla, el contrato de errores
`{"error": {"code", "message", "requestId"}}`, los logs estructurados y el límite de
solicitudes por actor en Redis (si Redis falla, no bloquea: fail-open).
"""
import base64
import json
import logging
import os
import re
import time
import uuid

from lambdas.shared.exceptions import DomainError, UnauthorizedError, ValidationError

logger = logging.getLogger("flashdelivery.http")
logger.setLevel(logging.INFO)
MAX_BODY = 16 * 1024


class Request:
    def __init__(self, event, params):
        self.event = event
        context = event.get("requestContext") or {}
        self.method = (context.get("http") or {}).get("method") or event.get("httpMethod") or "GET"
        self.path_params = params
        self.query = event.get("queryStringParameters") or {}
        self.headers = {str(k).lower(): v for k, v in (event.get("headers") or {}).items()}
        self.request_id = context.get("requestId") or uuid.uuid4().hex
        self._actor = None

    def json(self):
        raw = self.event.get("body")
        if raw in (None, ""):
            return {}
        if self.event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        if len(raw) > MAX_BODY:
            raise ValidationError("El cuerpo excede 16 KiB")
        try:
            data = json.loads(raw)
        except ValueError as exc:
            raise ValidationError("El cuerpo debe ser JSON válido") from exc
        if not isinstance(data, dict):
            raise ValidationError("El cuerpo debe ser un objeto JSON")
        return data

    @property
    def actor(self):
        if self._actor is None:
            from lambdas.identity.tokens import verify
            header = self.headers.get("authorization", "")
            if not header.startswith("Bearer "):
                raise UnauthorizedError("Inicia sesión para continuar")
            self._actor = verify(header[7:].strip())
        return self._actor

    @property
    def idempotency_key(self):
        value = self.headers.get("idempotency-key")
        if not value:
            raise ValidationError("Falta el encabezado Idempotency-Key")
        return value

    def page(self):
        limit = self.query.get("limit", "25")
        if not str(limit).isdigit() or not 1 <= int(limit) <= 100:
            raise ValidationError("limit debe ser un entero entre 1 y 100")
        page = {"limit": int(limit)}
        if self.query.get("cursor"):
            page["cursor"] = self.query["cursor"]
        return page


def response(status, body, request_id):
    return {"statusCode": status, "headers": {
        "Content-Type": "application/json", "Cache-Control": "no-store", "X-Request-Id": request_id},
        "body": json.dumps(body, ensure_ascii=False)}


def error_body(code, message, request_id):
    return {"error": {"code": code, "message": message, "requestId": request_id}}


def _compile(template):
    pattern = re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(template))
    # Admite el prefijo de etapa (p. ej. /local) que algunos emuladores dejan en rawPath.
    return re.compile(f"^(?:/[A-Za-z0-9_-]+)?{pattern}/?$")


def _rate_limited(request, route, limit):
    if not limit or request.method == "GET":
        return False
    try:
        from lambdas.shared.infrastructure.clients import shared_redis
        actor = request.actor.actor_id
        window = int(time.time() // 60)
        key = f"ratelimit:{actor}:{route}:{window}"
        client = shared_redis()
        count = client.incr(key)
        if count == 1:
            client.expire(key, 120)
        return count > limit
    except DomainError:
        return False  # sin actor válido: el caso de uso responderá 401
    except Exception:  # noqa: BLE001 - Redis caído no bloquea operaciones oficiales
        logger.warning(json.dumps({"event": "ratelimit_unavailable", "route": route}))
        return False


def router(routes):
    """Crea `main(event, context)` a partir de {"MÉTODO /plantilla": función(request)}."""
    table = []
    for spec, fn in routes.items():
        method, template = spec.split(" ", 1)
        table.append((method, template, _compile(template), fn))
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))

    def main(event, context):
        started = time.perf_counter()
        context_http = (event.get("requestContext") or {}).get("http") or {}
        method = context_http.get("method") or event.get("httpMethod") or "GET"
        path = event.get("rawPath") or context_http.get("path") or event.get("path") or "/"
        request, status, route, actor_id = None, 500, None, None
        try:
            for route_method, template, pattern, fn in table:
                match = pattern.match(path)
                if route_method == method and match:
                    route = f"{method} {template}"
                    request = Request(event, {k: v for k, v in match.groupdict().items()})
                    if _rate_limited(request, route, limit):
                        status = 429
                        return response(429, error_body("RATE_LIMITED", "Demasiadas solicitudes; espera un momento",
                                                        request.request_id), request.request_id)
                    status, body = fn(request)
                    actor_id = request._actor.actor_id if request._actor else None
                    return response(status, body, request.request_id)
            request = Request(event, {})
            status = 404
            return response(404, error_body("ROUTE_NOT_FOUND", "Ruta no encontrada", request.request_id),
                            request.request_id)
        except DomainError as error:
            status = error.status
            request_id = request.request_id if request else uuid.uuid4().hex
            return response(error.status, error_body(error.code, error.message, request_id), request_id)
        except Exception:  # noqa: BLE001 - nunca filtrar trazas al cliente
            logger.exception("Error no controlado en %s", route)
            request_id = request.request_id if request else uuid.uuid4().hex
            return response(500, error_body("INTERNAL_ERROR", "Error interno", request_id), request_id)
        finally:
            # Log estructurado sin direcciones, tokens ni cuerpos.
            logger.info(json.dumps({"requestId": request.request_id if request else None, "route": route,
                                    "status": status, "actorId": actor_id,
                                    "durationMs": round((time.perf_counter() - started) * 1000, 1)}))

    return main
