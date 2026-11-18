"""Última muestra efímera: comparación y límite por pedido/repartidor en Lua."""
import json
import os
from typing import Protocol


class LocationStore(Protocol):
    def publish(self, order_id, courier_id, point, now): ...
    def latest(self, order_id): ...
    def clear(self, order_id): ...
    def stop(self, order_id, now): ...


def location_key(order_id):
    return f"tracking:order:{order_id}:latest"


PUBLISH = """
local previous = redis.call('GET', KEYS[1])
if previous then
  local old = cjson.decode(previous)
  if old.stoppedAt and (tonumber(ARGV[2]) <= old.stoppedAt or tonumber(ARGV[5]) <= old.stoppedAt) then return 0 end
  if old.epoch and tonumber(ARGV[2]) <= old.epoch then return 0 end
  local incoming = cjson.decode(ARGV[1])
  if old.sequence and incoming.sequence and incoming.sequence <= old.sequence then return 0 end
end
if redis.call('EXISTS', KEYS[2]) == 1 or redis.call('EXISTS', KEYS[3]) == 1 then return -1 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
redis.call('SET', KEYS[2], '1', 'PX', ARGV[4])
redis.call('SET', KEYS[3], '1', 'PX', ARGV[4])
return 1
"""


class RedisLocationStore:
    def __init__(self, client):
        self.client = client
        self.ttl = int(os.getenv("LOCATION_TTL_SECONDS", "120"))
        self.interval = int(os.getenv("LOCATION_MIN_INTERVAL_MS", "3000"))

    def publish(self, order_id, courier_id, point, now):
        document = {**point, "courierId": courier_id}
        return int(self.client.eval(PUBLISH, 3, location_key(order_id),
            f"tracking:rate:order:{order_id}", f"tracking:rate:courier:{courier_id}",
            json.dumps(document), point["epoch"], self.ttl, self.interval, now))

    def latest(self, order_id):
        raw = self.client.get(location_key(order_id))
        return json.loads(raw) if raw else None

    def clear(self, order_id):
        self.client.delete(location_key(order_id))

    def stop(self, order_id, now):
        # Tombstone sin coordenadas: una petición atrasada no restaura lo que se dejó de compartir.
        self.client.set(location_key(order_id), json.dumps({"stoppedAt": now}), ex=self.ttl)
