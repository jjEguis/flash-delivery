"""SPEC-06: carga sintética y mediciones reproducibles sobre MiniStack y Redis locales.

Uso (desde cdk-dev, tras `python -m scripts.provision`):
    python -m scripts.benchmark --orders 10000
    python -m scripts.benchmark --orders 100000 --samples 200

Crea un namespace BENCH_<id> con un comercio, una zona y N pedidos (META + vista de
estado), mide cada patrón de acceso frente a un Scan equivalente, la caché de Redis, 100
aceptaciones concurrentes y la API HTTP, escribe app/.local/benchmark.json y limpia sus
datos por claves exactas. El Scan solo existe aquí como comparación; ninguna ruta
operativa lo usa.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
import platform
import statistics
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from lambdas.analytics.service import cache_key, get_month_stats
from lambdas.couriers.repository import CouriersRepository, courier_profile
from lambdas.dispatch import service as dispatch
from lambdas.identity.contracts import ActorContext
from lambdas.orders.repository import OrdersRepository, order_meta, store_status_view
from lambdas.orders import service as orders_service
from lambdas.shared import clock
from lambdas.shared.config.settings import ROOT, Settings
from lambdas.shared.exceptions import ConflictError
from lambdas.shared.infrastructure.clients import DynamoDBAdapter, redis_client
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import serialize
from lambdas.stores.repository import StoresRepository, store_profile
from lambdas.tracking.tokens import issue_token

STATUSES = ["PENDING", "ASSIGNED", "PICKED_UP", "DELIVERED", "CANCELLED"]


def percentiles(samples):
    ordered = sorted(samples)
    pick = lambda q: ordered[min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))]
    return {"n": len(ordered), "p50_ms": round(pick(0.50), 2), "p95_ms": round(pick(0.95), 2),
            "mean_ms": round(statistics.fmean(ordered), 2), "max_ms": round(ordered[-1], 2)}


def timed(fn, samples):
    results, last = [], None
    for _ in range(samples):
        start = time.perf_counter()
        last = fn()
        results.append((time.perf_counter() - start) * 1000)
    return percentiles(results), last


def synthetic_orders(namespace, store_id, zone_id, count):
    base = clock.now()
    for i in range(count):
        status = STATUSES[i % len(STATUSES)]
        order_id = f"{namespace}_o{i:06d}"
        created = f"2026-0{1 + i % 9}-{1 + i % 28:02d}T{i % 24:02d}:{i % 60:02d}:{(i // 60) % 60:02d}.{i % 1000000:06d}Z"
        order = order_meta(order_id=order_id, store_id=store_id, zone_id=zone_id, created_at=created,
                           updated_at=max(created, base) if status != "PENDING" else created,
                           pickup_address="Origen sintético", dropoff_address="Destino sintético", fee_minor=5000,
                           currency="COP", tracking_token_hash=issue_token(order_id)[1], status=status,
                           courier_id=None if status in {"PENDING"} else f"{namespace}_c0")
        yield order
        yield store_status_view(order)


def batch_write(adapter, items, workers=8):
    table = adapter.settings.table_name
    chunks = [items[i:i + 25] for i in range(0, len(items), 25)]

    def write(chunk):
        client = DynamoDBAdapter().client
        request = {table: [{"PutRequest": {"Item": serialize(item)}} for item in chunk]}
        while request:
            response = client.batch_write_item(RequestItems=request)
            request = response.get("UnprocessedItems") or {}
        client.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(write, chunks))


def batch_delete(adapter, key_list, workers=8):
    table = adapter.settings.table_name
    chunks = [key_list[i:i + 25] for i in range(0, len(key_list), 25)]

    def delete(chunk):
        client = DynamoDBAdapter().client
        request = {table: [{"DeleteRequest": {"Key": serialize(key)}} for key in chunk]}
        while request:
            request = client.batch_write_item(RequestItems=request).get("UnprocessedItems") or {}
        client.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(delete, chunks))


def scan_store_orders(adapter, store_id, limit):
    """Comparación: los 25 pedidos más recientes del comercio SIN índice.

    Un Scan no ordena: para conocer los más recientes hay que leer toda la tabla,
    filtrar y ordenar en la aplicación. Se cuentan los ítems devueltos por página
    (`Count`) para no depender del `ScannedCount` del emulador."""
    found, read, pages, start_key = [], 0, 0, None
    while True:
        args = {}
        if start_key:
            args["ExclusiveStartKey"] = start_key
        response = adapter.client.scan(TableName=adapter.settings.table_name, **args)
        read += response.get("Count", len(response["Items"]))
        found += [item for item in response["Items"]
                  if item.get("entityType", {}).get("S") == "ORDER" and item.get("storeId", {}).get("S") == store_id]
        pages += 1
        start_key = response.get("LastEvaluatedKey")
        if not start_key:
            break
    latest = sorted(found, key=lambda item: item["createdAt"]["S"], reverse=True)[:limit]
    return {"items_read": read, "matched": len(found), "returned": len(latest), "pages": pages}


def query_items_read(adapter, index, partition, prefix, limit):
    response = adapter.client.query(
        TableName=adapter.settings.table_name, IndexName=index, Limit=limit, ScanIndexForward=False,
        KeyConditionExpression="#pk = :pk AND begins_with(#sk, :p)",
        ExpressionAttributeNames={"#pk": index + "PK", "#sk": index + "SK"},
        ExpressionAttributeValues=serialize({":pk": partition, ":p": prefix}))
    return {"items_read": response.get("ScannedCount", response["Count"]), "returned": response["Count"]}


def http_latency(settings, samples):
    outputs = json.loads((ROOT / ".local/outputs.json").read_text())
    base = f"{settings.endpoint}/_aws/execute-api/{outputs['ApiId']}/local"

    def get(path):
        with urlopen(Request(base + path), timeout=30) as response:
            response.read()

    result = {}
    for path in ("/api/v1/health", "/api/v1/zones"):
        start = time.perf_counter()
        get(path)
        first = (time.perf_counter() - start) * 1000
        stats, _ = timed(lambda: get(path), samples)
        result[path] = {"first_call_ms": round(first, 2), **stats}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--orders", type=int, default=10000)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--keep", action="store_true", help="no borrar los datos sintéticos")
    args = parser.parse_args()
    settings = Settings.load()
    adapter, cache = DynamoDBAdapter(settings), redis_client(settings)
    namespace = "BENCH_" + uuid4().hex[:8]
    store_id, zone_id = namespace + "_store", namespace + "_zone"
    report = {"namespace": namespace, "orders": args.orders, "samples": args.samples,
              "machine": {"platform": platform.platform(), "python": platform.python_version(),
                          "cpus": os.cpu_count(), "emulator": os.getenv("MINISTACK_IMAGE", "ministackorg/ministack:1.5.36")}}
    created_keys = [keys.profile(keys.store(store_id))]
    try:
        now = clock.now()
        adapter.transact_write_items([StoresRepository(adapter).build_put(store_profile(
            store_id=store_id, owner_id=store_id, zone_id=zone_id, name="Bench", enabled=True, created_at=now))])
        start = time.perf_counter()
        items = list(synthetic_orders(namespace, store_id, zone_id, args.orders))
        batch_write(adapter, items)
        report["load"] = {"items": len(items), "seconds": round(time.perf_counter() - start, 2),
                          "items_per_second": round(len(items) / (time.perf_counter() - start), 1)}
        created_keys += [{"PK": item["PK"], "SK": item["SK"]} for item in items]
        time.sleep(1)  # convergencia de GSI en el emulador

        repo = OrdersRepository(adapter)
        sample_id = f"{namespace}_o{args.orders // 2:06d}"
        patterns = {}
        patterns["AP03 GetItem pedido"], _ = timed(lambda: repo.get_order(sample_id), args.samples)
        patterns["AP05 Query GSI1 pedidos del comercio (25)"], page = timed(
            lambda: repo.list_store_orders(store_id, limit=25), args.samples)
        patterns["AP06 Query GSI2 por estado (25)"], _ = timed(
            lambda: repo.list_store_orders_by_status(store_id, "DELIVERED", limit=25), args.samples)
        patterns["AP08 Query GSI2 abiertos de zona (25)"], _ = timed(
            lambda: repo.list_open_orders(zone_id, limit=25), args.samples)
        report["patterns"] = patterns
        report["patterns_items_returned"] = len(page.items)
        report["items_read_AP05_query"] = query_items_read(adapter, "GSI1", keys.store(store_id), "ORDER#", 25)
        scan_samples = max(3, min(10, args.samples // 10))
        scan_stats, scan_info = timed(lambda: scan_store_orders(adapter, store_id, 25), scan_samples)
        report["scan_equivalent_AP05"] = {**scan_stats, **scan_info}

        # Redis: Cache-Aside de estadísticas (miss → hit) y TTL.
        store_actor = ActorContext(store_id, "STORE")
        month = clock.month_of(now)
        misses, hits = [], []
        for _ in range(args.samples):
            cache.delete(cache_key(store_id, month))
            t0 = time.perf_counter()
            assert get_month_stats(adapter, cache, store_actor, month)["source"] == "dynamodb"
            misses.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            assert get_month_stats(adapter, cache, store_actor, month)["source"] == "cache"
            hits.append((time.perf_counter() - t0) * 1000)
        report["cache_stats"] = {"miss": percentiles(misses), "hit": percentiles(hits),
                                 "ttl_seconds": cache.ttl(cache_key(store_id, month))}
        cache.delete(cache_key(store_id, month))

        # Concurrencia: 100 repartidores contra un pedido nuevo.
        couriers = [f"{namespace}_c{n}" for n in range(100)]
        repo_c = CouriersRepository(adapter)
        profiles = [repo_c.build_put(courier_profile(courier_id=c, owner_id=c, zone_id=zone_id, name=c, enabled=True,
                                                     available=True, created_at=now)) for c in couriers]
        adapter.transact_write_items(profiles)
        created_keys += [k for c in couriers for k in (keys.profile(keys.courier(c)), keys.active(c))]
        race_order = orders_service.create_order(adapter, store_actor, request_id="bench_race", pickup_address="A",
                                                 dropoff_address="B", fee_minor=3000)["orderId"]
        created_keys += [keys.meta(race_order), keys.store_view(store_id, race_order),
                         keys.request(keys.request_scope(store_id, "orders.create.v1"), "bench_race")]

        def accept(courier_id):
            try:
                t0 = time.perf_counter()
                dispatch.accept_order(DynamoDBAdapter(settings), ActorContext(courier_id, "COURIER"), race_order,
                                      request_id="bench_accept")
                return "won", (time.perf_counter() - t0) * 1000
            except ConflictError as error:
                return error.code, (time.perf_counter() - t0) * 1000

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=32) as pool:
            outcomes = list(pool.map(accept, couriers))
        codes = {}
        for code, _ in outcomes:
            codes[code] = codes.get(code, 0) + 1
        report["concurrency_100_accepts"] = {"outcomes": codes, "wall_seconds": round(time.perf_counter() - start, 2),
                                             "latency": percentiles([ms for _, ms in outcomes])}
        events = repo.list_events(race_order, limit=100).items
        created_keys += [{"PK": e["PK"], "SK": e["SK"]} for e in events]
        created_keys += [keys.courier_view(c, race_order) for c in couriers]
        created_keys += [keys.request(keys.request_scope(c, "dispatch.accept.v1"), "bench_accept") for c in couriers]

        report["http"] = http_latency(settings, min(args.samples, 50))
    finally:
        if not args.keep:
            batch_delete(adapter, created_keys)
            report["cleanup_keys"] = len(created_keys)
        cache.close()
    output = ROOT / ".local" / "benchmark.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
