"""SPEC-08: endpoints desplegados y Lua en Redis real, sin servicios AWS reales."""
from datetime import datetime, timezone
import time
from uuid import uuid4

import pytest
from tests.integration.api_client import Api
from lambdas.shared.infrastructure.clients import redis_client
from lambdas.tracking.location_store import location_key, RedisLocationStore

pytestmark = pytest.mark.integration


@pytest.fixture
def api():
    client=Api()
    yield client
    client.cleanup()


def test_real_geo_flow_and_cleanup(api):
    run=uuid4().hex[:8]
    store,courier,outsider=f'geo_s{run}',f'geo_c{run}',f'geo_x{run}'
    tokens={name:api.login(name,role) for name,role in [(store,'STORE'),(courier,'COURIER'),(outsider,'STORE')]}
    admin=api.login('admin','ADMIN')
    for who,kind in [(store,'stores'),(outsider,'stores'),(courier,'couriers')]:
        assert api.call('POST',f'/api/v1/{kind}',{'name':'Prueba GPS','zoneId':'centro'},tokens[who])[0]==201
        assert api.call('PATCH',f'/api/v1/admin/{kind}/{who}',{'enabled':True},admin)[0]==200
    api.call('PATCH','/api/v1/couriers/me/availability',{'available':True},tokens[courier])
    status,order=api.call('POST','/api/v1/orders',{'pickupAddress':'A de prueba','dropoffAddress':'B de prueba','feeMinor':5000},tokens[store],key='geo_create')
    assert status==201,order
    order_id=order['orderId']; api.created['orders'].add(order_id);api.track(store,'orders.create.v1','geo_create')
    assert api.call('POST',f'/api/v1/orders/{order_id}/accept',token=tokens[courier],key='geo_accept')[0]==200
    api.track(courier,'dispatch.accept.v1','geo_accept')
    url=f'/api/v1/orders/{order_id}/location'; public=f"/api/v1/tracking/{order['trackingToken']}/location"
    p={'latitude':11.2408,'longitude':-74.199,'accuracyMeters':12.5,'recordedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'source':'SIMULATED'}
    status,result=api.call('POST',url,p,tokens[courier]); assert status==202 and result['accepted'],result
    assert api.call('GET',url,token=tokens[outsider])[0]==404
    assert api.call('GET',public)[1]['location']['source']=='SIMULATED'
    old={**p,'recordedAt':datetime.fromtimestamp(time.time()-30,timezone.utc).isoformat().replace('+00:00','Z')}
    assert api.call('POST',url,old,tokens[courier])[1]['accepted'] is False
    r=redis_client()
    try:
        assert 0<r.ttl(location_key(order_id))<=120
        assert api.call('DELETE',url,token=tokens[courier])[0]==204
        assert 'latitude' not in r.get(location_key(order_id))
        assert api.call('GET',public)[1]['location'] is None
        assert api.call('DELETE',f'/api/v1/orders/{order_id}/tracking-token',token=tokens[store])[0]==204
        assert api.call('GET',public)[0]==404
        for action in ['pickup','deliver']:
            api.track(courier,f'dispatch.{action}.v1','geo_'+action)
            assert api.call('POST',f'/api/v1/orders/{order_id}/{action}',token=tokens[courier],key='geo_'+action)[0]==200
        assert r.get(location_key(order_id)) is None
        assert api.call('POST',url,p,tokens[courier])[0]==409
    finally:r.close()


def test_real_redis_atomic_out_of_order_concurrency():
    from concurrent.futures import ThreadPoolExecutor
    r=redis_client(); order='geo_'+uuid4().hex; courier='geo_'+uuid4().hex
    store=RedisLocationStore(r); store.interval=1
    def send(index):
        p={'latitude':11.2,'longitude':-74.1,'recordedAt':str(index),'source':'SIMULATED','epoch':index}
        return store.publish(order,courier,p,time.time())
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(send,range(1,101)))
        time.sleep(.01); send(100)
        assert store.latest(order)['epoch']==100
        assert 0<r.ttl(location_key(order))<=120
        store.ttl=1; time.sleep(.01); send(101); time.sleep(1.1)
        assert store.latest(order) is None
    finally:
        r.delete(location_key(order),f'tracking:rate:order:{order}',f'tracking:rate:courier:{courier}');r.close()
