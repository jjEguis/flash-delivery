"""AP10: lectura de presencia; no adjudica pedidos ni cambia disponibilidad oficial."""
import json
import math
from lambdas.shared.storage import keys
from lambdas.shared.storage.repository import Page, page_limit, encode_cursor, decode_cursor


def zone_key(zone_id):
    return "couriers:available:" + keys.identifier(zone_id)


def heartbeat_key(courier_id):
    return "courier:heartbeat:" + keys.identifier(courier_id)


class AvailabilityRepository:
    def __init__(self, client):
        self.client = client

    def list_present(self, zone_id, *, now, window=60, limit=25, cursor=None):
        page_limit(limit)
        if not isinstance(now, (int, float)) or not math.isfinite(now) or now < 0:
            raise ValueError("now debe ser epoch válido")
        if type(window) is not int or window <= 0:
            raise ValueError("window debe ser entero positivo")
        scope = f"presence:{keys.identifier(zone_id)}:{window}"
        last = None
        if cursor:
            position = decode_cursor(cursor, scope)
            score = position.get("score")
            if (set(position) != {"score", "courierId"} or type(score) not in (int, float)
                    or not math.isfinite(score)):
                raise ValueError("Cursor de presencia inválido")
            last = (score, keys.identifier(position["courierId"]))
        minimum = max(now - window, last[0]) if last else now - window
        items, offset = [], 0
        # Redis puede contener miembros sin heartbeat: continuar hasta completar página.
        while len(items) <= limit:
            candidates = self.client.zrangebyscore(zone_key(zone_id), minimum, now,
                                                    start=offset, num=100, withscores=True)
            if not candidates:
                break
            offset += len(candidates)
            for courier_id, score in candidates:
                try:
                    keys.identifier(courier_id)
                except ValueError:
                    continue
                if last and (score, courier_id) <= last:
                    continue
                raw = self.client.get(heartbeat_key(courier_id))
                try:
                    presence = json.loads(raw) if raw else {}
                except (ValueError, TypeError):
                    continue
                if (not isinstance(presence, dict) or presence.get("zoneId") != zone_id
                        or presence.get("lastHeartbeatEpoch") != score):
                    continue
                items.append({"courierId": courier_id, "zoneId": zone_id, "lastHeartbeatEpoch": score})
                if len(items) > limit:
                    break
        next_cursor = None
        if len(items) > limit:
            tail = items[limit - 1]
            next_cursor = encode_cursor(scope, {"score": tail["lastHeartbeatEpoch"], "courierId": tail["courierId"]})
        return Page(items[:limit], next_cursor)
