"""SPEC-08 v2: contratos, ruta por fase, progreso/ETA y control de concurrencia."""
import json
import time
import pytest

from lambdas.identity.contracts import ActorContext
from lambdas.orders import handler as orders
from lambdas.tracking import handler as tracking
from lambdas.tracking.location_store import RedisLocationStore, location_key
from lambdas.tracking.routes import route_key, get_route
from lambdas.tracking.routing import OsrmRoutingProvider, RoutingUnavailable
from lambdas.tracking.progress import project
from lambdas.shared.infrastructure import clients
from tests.http_helpers import invoke
from tests.test_gps_tracking import geo, point, call
from tests.test_http_base_flow import STORE, COURIER, OTHER_STORE

def act(order,action,actor):
    from lambdas.dispatch import handler as dispatch
    return invoke(dispatch.main,'POST',f"/api/v1/orders/{order['orderId']}/{action}",actor=actor,key=action+'_'+order['orderId'])


PICKUP = {'latitude':11.244, 'longitude':-74.211}
DROPOFF = {'latitude':11.237, 'longitude':-74.201}


class Road:
    def __init__(self): self.calls=[]; self.down=False
    def route(self, origin, destination):
        self.calls.append((origin, destination))
        if self.down: raise RoutingUnavailable()
        coordinates = [[origin['longitude'], origin['latitude']], [destination['longitude'], destination['latitude']]]
        return {'geometry':{'type':'LineString','coordinates':coordinates},'distanceMeters':1000.,'durationSeconds':100.,
                'segmentDurations':[100.], 'segmentDistances':[1000.], 'steps':[]}


@pytest.fixture
def road_order(geo, monkeypatch):
    _, cache = geo
    road = Road()
    monkeypatch.setattr(OsrmRoutingProvider, 'route', road.route)
    body = {'pickupAddress':'Recogida', 'dropoffAddress':'Entrega', 'feeMinor':5000,
            'pickupLocation':PICKUP,'dropoffLocation':DROPOFF}
    status, order = invoke(orders.main,'POST','/api/v1/orders',actor=STORE,key='v2_create',body=body)
    assert status == 201, order
    # El fixture base tiene un pedido activo; cancelarlo libera al repartidor.
    assert act(geo[0], 'cancel', STORE)[0] == 200
    from lambdas.dispatch import handler as dispatch
    assert invoke(dispatch.main,'POST',f"/api/v1/orders/{order['orderId']}/accept",actor=COURIER,key='v2_accept')[0] == 200
    return order, cache, road


def route(order, actor=COURIER, public=False):
    path = f"/api/v1/tracking/{order['trackingToken']}/route" if public else f"/api/v1/orders/{order['orderId']}/route"
    return invoke(tracking.main, 'GET', path, actor=None if public else actor)


def publish(order, cache, latitude=11.25, longitude=-74.215, **extra):
    cache.delete(f"tracking:rate:order:{order['orderId']}", 'tracking:rate:courier:rep1')
    result = call(order, 'POST', body=point(latitude=latitude,longitude=longitude,**extra))
    assert result[0] == 202, result
    return result[1]


def test_optional_coordinates_compatible_and_idempotent(road_order):
    order, _, _ = road_order
    assert order['pickupLocation'] == PICKUP and order['dropoffLocation'] == DROPOFF
    fetched = invoke(orders.main,'GET',f"/api/v1/orders/{order['orderId']}",actor=STORE)[1]
    assert fetched['pickupLocation'] == PICKUP and 'pickupCoordinates' not in fetched
    body={'pickupAddress':'Recogida','dropoffAddress':'Entrega','feeMinor':5000,'pickupLocation':PICKUP,'dropoffLocation':DROPOFF}
    status,retry=invoke(orders.main,'POST','/api/v1/orders',actor=STORE,key='v2_create',body=body)
    assert status==201 and retry['orderId']==order['orderId'] and retry['trackingToken']==order['trackingToken']
    changed={**body,'dropoffLocation':{**DROPOFF,'latitude':11.236}}
    assert invoke(orders.main,'POST','/api/v1/orders',actor=STORE,key='v2_create',body=changed)[0]==409


@pytest.mark.parametrize('location', [{'latitude':91,'longitude':-74.2},{'latitude':11.2,'longitude':0},{'latitude':True,'longitude':-74.2},{'latitude':float('nan'),'longitude':-74.2}])
def test_creation_rejects_invalid_or_outside_coverage(geo, location):
    body={'pickupAddress':'A','dropoffAddress':'B','feeMinor':5000,'pickupLocation':location,'dropoffLocation':DROPOFF}
    assert invoke(orders.main,'POST','/api/v1/orders',actor=STORE,key='invalid_coord',body=body)[0] == 400


def test_no_origin_before_sample_permissions_and_public_minimum(road_order):
    order, cache, road = road_order
    status, result = route(order)
    assert status == 200 and result['points']['pickup'] == PICKUP and result['route'] is None and not road.calls
    assert route(order,OTHER_STORE)[0] == 404
    publish(order,cache,sequence=1,headingDegrees=80,speedMps=5)
    result=route(order)[1]['route']
    assert result['phase']=='ASSIGNED' and result['etaSeconds'] is not None and road.calls[-1][1]==PICKUP
    assert len(road.calls)==1
    public=route(order,public=True)[1]
    assert public['route']['routeVersion']==result['routeVersion']
    assert all(x not in json.dumps(public) for x in ['courierId','storeId','Address','segmentDurations','steps'])
    assert route(order)[0]==200 and len(road.calls)==1


def test_progress_eta_phase_change_and_terminal_hiding(road_order):
    order,cache,road=road_order
    publish(order,cache)
    before=route(order)[1]['route']
    publish(order,cache,latitude=11.247,longitude=-74.213)
    after=route(order)[1]['route']
    assert after['remainingMeters'] < before['remainingMeters'] and after['etaSeconds'] < before['etaSeconds']
    assert len(road.calls)==1
    assert act(order,'pickup',COURIER)[0]==200
    changed=route(order)[1]['route']
    assert changed['phase']=='PICKED_UP' and road.calls[-1][1]==DROPOFF and changed['routeVersion'] != before['routeVersion']
    assert act(order,'deliver',COURIER)[0]==200
    # Incluso con snapshot residual, el estado oficial oculta datos.
    cache.set(route_key(order['orderId'],'PICKED_UP'),json.dumps(changed),ex=120)
    assert route(order,public=True)[1]['route'] is None
    assert route(order,public=True)[1]['points'] is None


def test_deviation_three_samples_cooldown_and_lock(road_order):
    order,cache,road=road_order
    publish(order,cache)
    cooldown=f"tracking:order:{order['orderId']}:routing-cooldown"
    for _ in range(3): publish(order,cache,latitude=11.26,longitude=-74.23)
    off=route(order)[1]['route']
    assert off['offRoute'] and off['etaSeconds'] is None and len(road.calls)==1
    cache.delete(cooldown)
    lock=f"tracking:order:{order['orderId']}:routing-lock"
    cache.set(lock,'other',ex=10)
    assert route(order)[0]==200 and len(road.calls)==1
    cache.delete(lock)
    new=route(order)[1]['route']
    assert len(road.calls)==2 and new['routeVersion'] != off['routeVersion']
    assert cache.get(lock) is None


def test_outage_retains_stale_route_and_position_expiry(road_order):
    order,cache,road=road_order
    publish(order,cache)
    road.down=True
    for _ in range(3): publish(order,cache,latitude=11.26,longitude=-74.23)
    cache.delete(f"tracking:order:{order['orderId']}:routing-cooldown")
    result=route(order)[1]['route']
    assert result['stale'] and result['etaSeconds'] is None
    cache.delete(location_key(order['orderId']))
    assert route(order)[1]['route'] is None


@pytest.mark.parametrize('extra',[{'sequence':-1},{'sequence':True},{'speedMps':float('inf')},{'speedMps':-1},{'headingDegrees':360}])
def test_invalid_movement(geo,extra):
    assert call(geo[0],'POST',body=point(**extra))[0]==422


def test_sequence_duplicate_does_not_refresh_ttl(geo):
    order,cache=geo
    assert call(order,'POST',body=point(sequence=7))[1]['accepted']
    cache.expire(location_key(order['orderId']),40)
    assert call(order,'POST',body=point(sequence=7))[1]['accepted'] is False
    assert cache.ttl(location_key(order['orderId']))<=40


def test_simulation_requires_backend_development_flag(geo,monkeypatch):
    monkeypatch.setenv('TRACKING_SIMULATION_ENABLED','false')
    assert call(geo[0],'POST',body=point())[0]==403
    assert call(geo[0],'POST',body=point(source='BROWSER_GPS'))[0]==202


def test_provider_validates_noroute_malformed_and_timeout(monkeypatch):
    import lambdas.tracking.routing as routing
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,*args): return b'{"code":"NoRoute"}'
    monkeypatch.setattr(routing,'urlopen',lambda *a,**kw:Response())
    with pytest.raises(RoutingUnavailable): OsrmRoutingProvider().route(PICKUP,DROPOFF)
    def timeout(*a,**kw): raise TimeoutError()
    monkeypatch.setattr(routing,'urlopen',timeout)
    with pytest.raises(RoutingUnavailable): OsrmRoutingProvider().route(PICKUP,DROPOFF)


def test_progress_crossing_uses_previous_segment():
    route={'geometry':{'coordinates':[[0,0],[.001,.001],[0,.001],[.001,0]]},'distanceMeters':420,'durationSeconds':42,
           'segmentDurations':[15,12,15],'segmentDistances':[150,120,150]}
    first=project(route,{'longitude':.00049,'latitude':.00049,'epoch':10})
    second=project(route,{'longitude':.00051,'latitude':.00049,'epoch':11},first)
    assert second['segmentIndex']==0 and second['progressMeters']<160


def test_expired_lock_owner_cannot_publish_or_release_successor(road_order):
    order,cache,road=road_order
    publish(order,cache)
    cache.delete(route_key(order['orderId'],'ASSIGNED'),f"tracking:order:{order['orderId']}:routing-cooldown")
    lock=f"tracking:order:{order['orderId']}:routing-lock"
    class Successor:
        def route(self, origin, destination):
            cache.set(lock,'successor',ex=10)
            return road.route(origin,destination)
    result=get_route(clients.shared_adapter(),cache,actor=ActorContext(*COURIER),order_id=order['orderId'],provider=Successor())
    assert result['route'] is None
    assert cache.get(lock)=='successor'
    assert cache.get(route_key(order['orderId'],'ASSIGNED')) is None


def test_route_recalculated_after_configured_lifetime(road_order):
    order,cache,road=road_order
    publish(order,cache)
    key=route_key(order['orderId'],'ASSIGNED');snapshot=json.loads(cache.get(key))
    snapshot['calculatedEpoch']=time.time()-301;cache.set(key,json.dumps(snapshot),ex=300)
    cache.delete(f"tracking:order:{order['orderId']}:routing-cooldown")
    assert route(order)[1]['route']['routeVersion'] != snapshot['routeVersion']
    assert len(road.calls)==2


def test_terminal_transition_during_calculation_hides_all_route_data(road_order):
    from lambdas.identity.contracts import ActorContext
    order,cache,road=road_order
    publish(order,cache)
    cache.delete(route_key(order['orderId'],'ASSIGNED'),f"tracking:order:{order['orderId']}:routing-cooldown")
    class Closing:
        def route(self, origin, destination):
            assert act(order,'cancel',STORE)[0]==200
            return road.route(origin,destination)
    result=get_route(clients.shared_adapter(),cache,actor=ActorContext(*COURIER),order_id=order['orderId'],provider=Closing())
    assert result['status']=='CANCELLED' and result['route'] is None and result['points'] is None
