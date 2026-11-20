"""Perfiles de demostración ya habilitados para probar el frontend.

    python -m scripts.demo            # crea tienda_demo y rep_demo1..3 en la zona centro
    python -m scripts.demo --clean    # elimina esos perfiles (por claves exactas)

Después entra en http://127.0.0.1:8080 como Comercio «tienda_demo» o Repartidor
«rep_demo1». Los pedidos se crean desde la interfaz.
"""
import argparse

from lambdas.couriers.repository import CouriersRepository, courier_profile
from lambdas.shared import clock
from lambdas.shared.infrastructure.clients import DynamoDBAdapter
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import serialize
from lambdas.stores.repository import StoresRepository, store_profile

STORE = "tienda_demo"
COURIERS = ["rep_demo1", "rep_demo2", "rep_demo3"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zone", default="centro")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    adapter = DynamoDBAdapter()
    table = adapter.settings.table_name
    if args.clean:
        for key in [keys.profile(keys.store(STORE))] + [keys.profile(keys.courier(c)) for c in COURIERS]:
            adapter.client.delete_item(TableName=table, Key=serialize(key))
        print("Perfiles de demostración eliminados")
        return
    now = clock.now()
    items = [store_profile(store_id=STORE, owner_id=STORE, zone_id=args.zone, name="Tienda Demo",
                           enabled=True, created_at=now)]
    items += [courier_profile(courier_id=c, owner_id=c, zone_id=args.zone, name=f"Repartidor {i}",
                              enabled=True, available=True, created_at=now) for i, c in enumerate(COURIERS, 1)]
    for item in items:
        # Put directo (sin condición): repetir el script restablece los perfiles.
        adapter.client.put_item(TableName=table, Item=serialize(item))
    print(f"Listo: comercio {STORE} y repartidores {', '.join(COURIERS)} en la zona {args.zone}")


if __name__ == "__main__":
    main()
