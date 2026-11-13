"""Funciones puras de claves, con formatos de ordenamiento inequívocos."""
from datetime import datetime, timezone
import re

STATUSES = {"PENDING", "ASSIGNED", "PICKED_UP", "DELIVERED", "CANCELLED", "FAILED"}


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("ID inválido: usar 1–128 letras ASCII, números, guion o guion bajo")
    return value


def timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Fecha debe incluir zona horaria")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def month(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValueError("Mes debe tener formato YYYY-MM")
    datetime.strptime(value, "%Y-%m")
    return value


def status(value):
    if not isinstance(value, str) or value not in STATUSES:
        raise ValueError("Estado de pedido inválido")
    return value


def store(store_id):
    return f"STORE#{identifier(store_id)}"


def courier(courier_id):
    return f"COURIER#{identifier(courier_id)}"


def order(order_id):
    return f"ORDER#{identifier(order_id)}"


def key(pk, sk):
    return {"PK": pk, "SK": sk}


def profile(pk):
    return key(pk, "PROFILE")


def meta(order_id):
    return key(order(order_id), "META")


def active(courier_id):
    return key(courier(courier_id), "ACTIVE")


def event(order_id, occurred_at, event_id):
    return key(order(order_id), f"EVENT#{timestamp(occurred_at)}#{identifier(event_id)}")


def history(created_at, order_id):
    return f"ORDER#{timestamp(created_at)}#{identifier(order_id)}"


def created(created_at, order_id):
    return f"CREATED#{timestamp(created_at)}#{identifier(order_id)}"


def zone_open(zone_id):
    return f"ZONE#{identifier(zone_id)}#OPEN"


def store_state(store_id, state):
    return f"{store(store_id)}#{status(state)}"


def store_view(store_id, order_id):
    return key(store(store_id), f"STATUS#{identifier(order_id)}")


def courier_view(courier_id, order_id):
    return key(courier(courier_id), order(order_id))


def stats(store_id, year_month):
    return key(store(store_id), f"STATS#{month(year_month)}")


def request_scope(actor_id, operation):
    identifier(actor_id)
    if not isinstance(operation, str) or not re.fullmatch(r"[a-z][a-z0-9._-]{0,63}", operation):
        raise ValueError("Operación idempotente inválida")
    return f"{actor_id}:{operation}"


def request(scope, request_id):
    if not isinstance(scope, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", scope):
        raise ValueError("Scope inválido")
    return key(f"REQUEST#{scope}#{identifier(request_id)}", "IDEMPOTENCY")
