"""Datos aislados del smoke de navegador GPS; se limpian por claves exactas."""
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

from tests.integration.api_client import Api


def create(path):
    api = Api()
    try:
        run = uuid4().hex[:8]
        store, courier = f'geo_ui_s{run}', f'geo_ui_c{run}'
        sessions = {}
        for name, role in [(store, 'STORE'), (courier, 'COURIER')]:
            sessions[role] = {'token': api.login(name, role), 'actor': {'actorId': name, 'role': role}}
        admin = api.login('admin', 'ADMIN')
        for who, kind, role in [(store, 'stores', 'STORE'), (courier, 'couriers', 'COURIER')]:
            assert api.call('POST', f'/api/v1/{kind}', {'name': 'Demo GPS aislada', 'zoneId':'centro'}, sessions[role]['token'])[0] == 201
            assert api.call('PATCH', f'/api/v1/admin/{kind}/{who}', {'enabled':True}, admin)[0] == 200
        token = sessions['COURIER']['token']
        api.call('PATCH', '/api/v1/couriers/me/availability', {'available':True}, token)
        status, order = api.call('POST', '/api/v1/orders', {'pickupAddress':'Origen de prueba', 'dropoffAddress':'Destino de prueba', 'feeMinor':5000,
            'pickupLocation':{'latitude':11.237,'longitude':-74.201},
            'dropoffLocation':{'latitude':11.235,'longitude':-74.19}}, sessions['STORE']['token'], key='geo_ui_create')
        assert status == 201
        api.created['orders'].add(order['orderId']); api.track(store, 'orders.create.v1', 'geo_ui_create')
        assert api.call('POST', f"/api/v1/orders/{order['orderId']}/accept", token=token, key='geo_ui_accept')[0] == 200
        api.track(courier, 'dispatch.accept.v1', 'geo_ui_accept')
        data = {'sessions':sessions, 'order':order, 'created':{key:list(value) for key,value in api.created.items()}}
        # No imprimir credenciales ni enlaces públicos en consola.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd,'w') as output: json.dump(data,output)
    except Exception:
        api.cleanup()
        raise


def journey(path):
    """Reservar identificadores para registrar/habilitar desde la UI, sin preaprobar."""
    from lambdas.shared.config.settings import Settings
    Settings.load()
    run = uuid4().hex[:8]
    actors = {'STORE': 'journey_s'+run, 'COURIER': 'journey_c'+run}
    data = {'actors': actors, 'zone': 'oriente', 'adminCode': os.getenv('DEV_ADMIN_CODE', 'admin-local'),
            'created': {'stores':[actors['STORE']], 'couriers':[actors['COURIER']], 'orders':[], 'requests':[]}}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(data, output)


def cleanup(path):
    data = json.loads(Path(path).read_text())
    api = Api()
    api.created = {key:{tuple(value) if isinstance(value,list) else value for value in values} for key,values in data['created'].items()}
    if data.get('zone'):
        from lambdas.shared.infrastructure.clients import redis_client
        from lambdas.availability.repository import zone_key
        cache = redis_client()
        try:
            for courier in api.created['couriers']:
                cache.zrem(zone_key(data['zone']), courier)
        finally:
            cache.close()
    api.cleanup()
    Path(path).unlink()


if __name__ == '__main__':
    operation, path = sys.argv[1:]
    {'create':create, 'journey':journey, 'cleanup':cleanup}[operation](path)
