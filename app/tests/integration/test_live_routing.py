"""OSRM/Redis/MiniStack reales: ruta HTTP, progreso, seguridad y latencias observadas."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import statistics
import re
import time
from uuid import uuid4
from pathlib import Path
import pytest
from tests.integration.api_client import Api
from lambdas.shared.infrastructure.clients import redis_client
from lambdas.tracking.routing import OsrmRoutingProvider, RoutingUnavailable
from lambdas.tracking.routes import clear_routes

pytestmark=pytest.mark.integration


def test_local_osrm_route_and_unavailable():
    provider=OsrmRoutingProvider()
    route=provider.route({'longitude':-74.211,'latitude':11.244},{'longitude':-74.201,'latitude':11.237})
    assert len(route['geometry']['coordinates'])>2
    assert route['distanceMeters']>100 and route['durationSeconds']>0
    assert len(route['segmentDurations'])==len(route['geometry']['coordinates'])-1
    with pytest.raises(RoutingUnavailable):
        OsrmRoutingProvider(url='http://osrm:1',timeout=.3).route({'longitude':-74.211,'latitude':11.244},{'longitude':-74.201,'latitude':11.237})
    with pytest.raises(RoutingUnavailable):
        provider.route({'longitude':-74.27,'latitude':11.35},{'longitude':-74.201,'latitude':11.237})


def test_real_live_route_flow_and_latency():
    api=Api(); cache=redis_client(); timings=[]; operations=set(); order_id=None
    def request(method,path,*args,**kwargs):
        started=time.perf_counter(); result=api.call(method,path,*args,**kwargs)
        timings.append((time.perf_counter()-started)*1000)
        normalized=re.sub(r'/orders/[^/]+/', '/orders/{orderId}/', path.split('?')[0])
        normalized=re.sub(r'/tracking/[^/]+', '/tracking/{token}', normalized)
        normalized=re.sub(r'/admin/(stores|couriers)/[^/]+', r'/admin/\1/{actorId}', normalized)
        operations.add(method+' '+normalized);return result
    def send(coordinate, sequence):
        cache.delete(f'tracking:rate:order:{order_id}',f'tracking:rate:courier:{courier}')
        payload={'latitude':coordinate[1],'longitude':coordinate[0],'accuracyMeters':10,'source':'SIMULATED',
                 'recordedAt':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'sequence':sequence,'speedMps':8,'headingDegrees':90}
        status, result=request('POST',f'/api/v1/orders/{order_id}/location',payload,courier_token)
        assert status==202 and result['accepted'],result
        return payload
    try:
        run=uuid4().hex[:8];store,courier,other='r_s'+run,'r_c'+run,'r_x'+run
        store_token=api.login(store,'STORE');courier_token=api.login(courier,'COURIER');other_token=api.login(other,'STORE');admin=api.login('admin','ADMIN')
        for actor,kind,token in [(store,'stores',store_token),(courier,'couriers',courier_token),(other,'stores',other_token)]:
            assert request('POST',f'/api/v1/{kind}',{'name':'Ruta IT','zoneId':'centro'},token)[0]==201
            assert request('PATCH',f'/api/v1/admin/{kind}/{actor}',{'enabled':True},admin)[0]==200
        assert request('GET','/api/v1/zones')[0]==200
        assert request('GET','/api/v1/auth/me',token=courier_token)[0]==200
        assert request('PATCH','/api/v1/couriers/me/availability',{'available':True},courier_token)[0]==200
        body={'pickupAddress':'Recogida de prueba','dropoffAddress':'Destino de prueba','feeMinor':5000,
              'pickupLocation':{'latitude':11.237,'longitude':-74.201},'dropoffLocation':{'latitude':11.235,'longitude':-74.19}}
        status,order=request('POST','/api/v1/orders',body,store_token,key='route_create')
        assert status==201,order
        order_id=order['orderId'];api.created['orders'].add(order_id);api.track(store,'orders.create.v1','route_create')
        assert request('POST',f'/api/v1/orders/{order_id}/accept',token=courier_token,key='route_accept')[0]==200
        api.track(courier,'dispatch.accept.v1','route_accept')
        internal=f'/api/v1/orders/{order_id}/route';public=f"/api/v1/tracking/{order['trackingToken']}/route"
        assert request('GET',internal,token=other_token)[0]==404
        assert request('GET',internal,token=store_token)[1]['route'] is None
        sample=send([-74.211,11.244],1)
        first=request('GET',internal,token=store_token)[1]['route']
        assert first and first['phase']=='ASSIGNED' and first['etaSeconds']>0
        ttl=cache.ttl(f'tracking:order:{order_id}:latest')
        assert request('POST',f'/api/v1/orders/{order_id}/location',sample,courier_token)[1]['accepted'] is False
        assert cache.ttl(f'tracking:order:{order_id}:latest')<=ttl
        coordinates=first['geometry']['coordinates']
        a,b=coordinates[:2]
        for sequence,fraction in enumerate([.1,.2,.3],2):
            send([a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction],sequence)
        progressed=request('GET',public)[1]['route']
        assert progressed['remainingMeters']<first['remainingMeters'] and progressed['etaSeconds']<first['etaSeconds']
        assert progressed['routeVersion']==first['routeVersion']
        assert 'steps' not in progressed and 'courierId' not in json.dumps(progressed)
        # No hay un recálculo OSRM por cada muestra; la versión permanece estable.
        for _ in range(10): assert request('GET',internal,token=store_token)[1]['route']['routeVersion']==first['routeVersion']
        # Tres muestras fuera de ruta; el cooldown impide recalcular en cada muestra.
        for sequence in range(5,8): send([-74.21,11.25],sequence)
        deviated=request('GET',internal,token=store_token)[1]['route']
        assert deviated['offRoute'] and deviated['etaSeconds'] is None and deviated['routeVersion']==first['routeVersion']
        assert int(cache.get(f'tracking:order:{order_id}:routing-calls') or 0)==1
        cache.expire(f'tracking:order:{order_id}:routing-cooldown',1);time.sleep(1.1)
        with ThreadPoolExecutor(max_workers=6) as pool:
            parallel=list(pool.map(lambda _:api.call('GET',internal,token=store_token),range(6)))
        assert all(status==200 for status,_ in parallel)
        recalculated=request('GET',internal,token=store_token)[1]['route']
        assert recalculated['routeVersion']!=first['routeVersion'] and not recalculated['offRoute']
        assert int(cache.get(f'tracking:order:{order_id}:routing-calls') or 0)==2
        assert request('POST',f'/api/v1/orders/{order_id}/pickup',token=courier_token,key='route_pickup')[0]==200
        api.track(courier,'dispatch.pickup.v1','route_pickup')
        picked=request('GET',internal,token=store_token)[1]['route']
        assert picked['phase']=='PICKED_UP' and picked['routeVersion']!=first['routeVersion']
        assert request('GET',f'/api/v1/orders/{order_id}/events',token=store_token)[0]==200
        assert request('GET',f"/api/v1/tracking/{order['trackingToken']}")[0]==200
        assert request('POST',f'/api/v1/orders/{order_id}/deliver',token=courier_token,key='route_deliver')[0]==200
        api.track(courier,'dispatch.deliver.v1','route_deliver')
        assert request('GET',public)[1]['route'] is None
        assert request('POST',f'/api/v1/orders/{order_id}/location',sample,courier_token)[0]==409
        assert request('DELETE',f'/api/v1/orders/{order_id}/tracking-token',token=store_token)[0]==204
        assert request('GET',public)[0]==404
        assert len(operations)>=10
        out=Path('.local/live-routing-metrics.json');out.parent.mkdir(exist_ok=True)
        sorted_times=sorted(timings)
        # No guardar URLs con token ni coordenadas; solo medidas agregadas.
        routing_calls=int(cache.get(f'tracking:order:{order_id}:routing-calls') or 0)
        assert routing_calls==3  # inicial, desvío y fase; las seis lecturas concurrentes solo provocan un recálculo
        out.write_text(json.dumps({'requests':len(timings),'distinctOperations':len(operations),
            'routingCalls':routing_calls,
            'p50Ms':round(statistics.median(timings),2),'p95Ms':round(sorted_times[int(.95*(len(sorted_times)-1))],2),
            'stableRouteReads':10,'samplesBeforePhaseChange':7,'routeVersionsBeforePhaseChange':1},indent=2))
    finally:
        if order_id: clear_routes(cache,order_id)
        cache.close();api.cleanup()
