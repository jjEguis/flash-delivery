"""Datos sintéticos idempotentes, con claves conocidas y limpieza sin Scan."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time

from lambdas.stores.repository import store_profile
from lambdas.couriers.repository import courier_profile, active_assignment, courier_order_view
from lambdas.orders.repository import order_meta, order_event, store_status_view
from lambdas.analytics.repository import store_stats
from lambdas.tracking.repository import tracking_token
from lambdas.availability.repository import zone_key, heartbeat_key
from lambdas.shared.storage.idempotency import idempotency_record
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import serialize, validate
from lambdas.shared.infrastructure.clients import DynamoDBAdapter, redis_client


def synthetic_items(namespace="SEED_demo"):
    keys.identifier(namespace)
    if not namespace.startswith("SEED_") or len(namespace) > 64:
        raise ValueError("namespace debe comenzar con SEED_ y tener hasta 64 caracteres")
    date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store_id, zone_id = namespace + "_store", namespace + "_zone"
    items = [store_profile(store_id=store_id, owner_id=namespace + "_owner", zone_id=zone_id,
                           name="Comercio sintético", enabled=True, created_at=date)]
    for i in range(1, 4):
        items.append(courier_profile(courier_id=f"{namespace}_c{i}", owner_id=f"{namespace}_u{i}",
                                     zone_id=zone_id, name=f"Repartidor sintético {i}", enabled=True,
                                     available=True, created_at=date))
    statuses = ["PENDING", "PENDING", "ASSIGNED", "PICKED_UP", "DELIVERED", "CANCELLED", "FAILED"]
    for i, status in enumerate(statuses, 1):
        order_id = f"{namespace}_o{i}"
        secret = hashlib.sha256(f"synthetic-only:{order_id}".encode()).hexdigest()
        _, digest = tracking_token(order_id, secret)
        courier_id = None
        if status in {"ASSIGNED", "PICKED_UP", "DELIVERED", "FAILED"}:
            courier_id = f"{namespace}_c{1 if status == 'ASSIGNED' else 2 if status == 'PICKED_UP' else 3}"
        created_at = date + timedelta(minutes=i)
        events = ["CREATED"]
        if status == "CANCELLED":
            events.append("CANCELLED")
        elif status != "PENDING":
            events.append("ASSIGNED")
            if status in {"PICKED_UP", "DELIVERED", "FAILED"}:
                events.append("PICKED_UP")
            if status in {"DELIVERED", "FAILED"}:
                events.append(status)
        order = order_meta(order_id=order_id, store_id=store_id, zone_id=zone_id,
                           created_at=created_at, updated_at=created_at + timedelta(seconds=5 * (len(events) - 1)),
                           pickup_address="Origen sintético", dropoff_address="Destino sintético",
                           fee_minor=5000, currency="COP", tracking_token_hash=digest,
                           status=status, courier_id=courier_id, version=len(events))
        items.extend([order, store_status_view(order)])
        for number, event_type in enumerate(events, 1):
            items.append(order_event(order_id, f"event_{i}_{number}", event_type,
                                     created_at + timedelta(seconds=5 * (number - 1))))
        if courier_id:
            items.append(courier_order_view(order))
        if status in {"ASSIGNED", "PICKED_UP"}:
            items.append(active_assignment(courier_id, order_id, created_at))
    items.append(store_stats(store_id, "2026-01", 1, 5000, date + timedelta(hours=1)))
    items.append(idempotency_record(keys.request_scope(namespace + "_owner", "orders.create.v1"),
                                    "demo_request", hashlib.sha256(b"synthetic-payload").hexdigest(),
                                    {"orderId": namespace + "_o1"}, date))
    return items


def seed(adapter, cache, namespace="SEED_demo", *, clean=False, now=None):
    items = synthetic_items(namespace)
    actions = []
    for item in items:
        validate(item)
        if clean:
            actions.append({"Delete": {"TableName": adapter.settings.table_name,
                                       "Key": serialize({name: item[name] for name in ("PK", "SK")})}})
        else:
            actions.append({"Put": {"TableName": adapter.settings.table_name, "Item": serialize(item)}})
    for offset in range(0, len(actions), 100):
        adapter.transact_write_items(actions[offset:offset + 100])
    epoch = time.time() if now is None else now
    for item in items:
        if item["entityType"] != "COURIER":
            continue
        courier_id, zone_id = item["courierId"], item["zoneId"]
        if clean:
            cache.delete(heartbeat_key(courier_id))
            cache.zrem(zone_key(zone_id), courier_id)
        else:
            cache.set(heartbeat_key(courier_id), json.dumps({"zoneId": zone_id, "lastHeartbeatEpoch": epoch}), ex=60)
            cache.zadd(zone_key(zone_id), {courier_id: epoch})
    return len(items)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", default="SEED_demo")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    # Valida antes de abrir conexiones; la limpieza nunca interpreta prefijos libres.
    synthetic_items(args.namespace)
    adapter, cache = DynamoDBAdapter(), redis_client()
    try:
        count = seed(adapter, cache, args.namespace, clean=args.clean)
        print(json.dumps({"namespace": args.namespace, "items": count, "clean": args.clean}))
    finally:
        adapter.client.close()
        cache.close()


if __name__ == "__main__":
    main()
