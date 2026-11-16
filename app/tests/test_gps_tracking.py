"""SPEC-08: HTTP, permisos, tokens, orden atómico, TTL y degradación sin red."""
from datetime import datetime, timezone
import json
import time

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from lambdas.dispatch import handler as dispatch
from lambdas.shared.infrastructure import clients
from lambdas.tracking import handler as tracking
from lambdas.tracking.access import TrackingAccess, access_key
from lambdas.tracking.location_store import location_key
from lambdas.shared.storage.model import serialize
from tests.http_helpers import invoke
from tests.test_http_base_flow import STORE, COURIER, OTHER_STORE, ADMIN, enabled_store, enabled_courier, new_order

OTHER_COURIER = ('rep2', 'COURIER')


@pytest.fixture
def geo(tabla_dynamodb, redis_fake, monkeypatch):
    monkeypatch.setitem(clients._SHARED, 'adapter', clients.DynamoDBAdapter(client=tabla_dynamodb))
    monkeypatch.setitem(clients._SHARED, 'redis', redis_fake)
    enabled_store(); enabled_store(OTHER_STORE)
    enabled_courier(); enabled_courier(OTHER_COURIER)
    order = new_order()[1]
    assert act(order, 'accept', COURIER)[0] == 200
    return order, redis_fake


def act(order, action, actor):
    return invoke(dispatch.main, 'POST', f"/api/v1/orders/{order['orderId']}/{action}", actor=actor, key=action)


def point(offset=0, **extra):
    return {'latitude':11.2408,'longitude':-74.199,'accuracyMeters':12.5,
            'recordedAt': datetime.fromtimestamp(time.time()+offset, timezone.utc).isoformat().replace('+00:00','Z'),
            'source':'SIMULATED', **extra}


def call(order, method='GET', *, actor=COURIER, body=None, public=False):
    path = f"/api/v1/tracking/{order['trackingToken']}/location" if public else f"/api/v1/orders/{order['orderId']}/location"
    return invoke(tracking.main, method, path, actor=None if public else actor, body=body)


def test_permissions_publish_and_minimal_public_response(geo):
    order, cache = geo
    assert call(order)[1]['location'] is None
    assert call(order,'POST',actor=None,body=point())[0] == 401
    assert call(order,'POST',actor=OTHER_COURIER,body=point())[0] == 403
    assert call(order,'POST',actor=STORE,body=point())[0] == 403
    assert call(order,actor=OTHER_STORE)[0] == 404
    assert call(order,actor=ADMIN)[0] == 403
    assert call(order,'POST',body=point())[0] == 202
    for kwargs in ({'actor':STORE},{'actor':COURIER},{'public':True}):
        status, result = call(order,**kwargs)
        assert status == 200 and result['freshness']=='FRESH'
        assert set(result)=={'orderId','status','updatedAt','location','freshness'}
        assert set(result['location'])=={'latitude','longitude','accuracyMeters','recordedAt','source'}
        assert all(private not in json.dumps(result) for private in ['courierId','storeId','Address','nonce','Hash'])
    assert 0 < cache.ttl(location_key(order['orderId'])) <= 120


@pytest.mark.parametrize('extra', [
    {'latitude':91}, {'latitude':True}, {'longitude':-181}, {'longitude':float('nan')},
    {'accuracyMeters':10**400}, {'source':[]}, {'accuracyMeters':-1}, {'accuracyMeters':None}, {'recordedAt':'ayer'},
    {'recordedAt':'2026-01-01T01:00:00+01:00'}, {'source':'REAL'}, {'courierId':'rep2'},
])
def test_invalid_samples(geo,extra):
    order,_=geo
    assert call(order,'POST',body=point(**extra))[0]==422


@pytest.mark.parametrize('offset', [-121,16])
def test_stale_or_future_timestamp_rejected(geo,offset):
    assert call(geo[0],'POST',body=point(offset))[0]==422


def test_ordering_rate_limit_stale_and_expired(geo,monkeypatch):
    order,cache=geo
    first=point(-45)
    assert call(order,'POST',body=first)[1]['accepted']
    assert call(order)[1]['freshness']=='STALE'
    assert call(order,'POST',body=point(-60))[1]['accepted'] is False
    assert call(order,'POST',body=first)[1]['accepted'] is False
    assert call(order,'POST',body=point())[0]==429
    cache.delete(f"tracking:rate:order:{order['orderId']}", 'tracking:rate:courier:rep1')
    assert call(order,'POST',body=point())[1]['accepted']
    assert call(order)[1]['freshness']=='FRESH'
    cache.delete(location_key(order['orderId']))
    assert call(order)[1]['freshness']=='UNAVAILABLE'


@pytest.mark.parametrize('ending', ['deliver','cancel','fail'])
def test_ending_clears_and_blocks_coordinates(geo,ending):
    order,cache=geo
    assert call(order,'POST',body=point())[0]==202
    if ending in {'deliver','fail'}: assert act(order,'pickup',COURIER)[0]==200
    actor = STORE if ending=='cancel' else ADMIN if ending=='fail' else COURIER
    assert act(order,ending,actor)[0]==200
    assert cache.get(location_key(order['orderId'])) is None
    assert call(order,'POST',body=point())[0]==409
    assert call(order,public=True)[1]['location'] is None


def test_stop_removes_coordinates_and_rejects_inflight_old_sample(geo):
    order,cache=geo
    old=point()
    call(order,'POST',body=old)
    assert call(order,'DELETE')[0]==204
    assert 'latitude' not in cache.get(location_key(order['orderId']))
    assert call(order,public=True)[1]['location'] is None
    assert call(order,'POST',body=old)[1]['accepted'] is False


def test_token_tampering_expiration_and_revocation(geo,monkeypatch):
    order,_=geo
    call(order,'POST',body=point())
    invalid={**order,'trackingToken':order['orderId']+'.'+'A'*43}
    assert call(invalid,public=True)[0]==404
    adapter=clients.shared_adapter()
    access=TrackingAccess(adapter).for_order(order['orderId'])
    assert access['nonce'] not in order['trackingToken']
    adapter.update_item(Key=serialize(access_key(order['orderId'])), UpdateExpression='SET expiresAt = :t',
                        ExpressionAttributeValues=serialize({':t':int(time.time())-1}))
    assert call(order,public=True)[0]==404
    adapter.update_item(Key=serialize(access_key(order['orderId'])), UpdateExpression='SET expiresAt = :t',
                        ExpressionAttributeValues=serialize({':t':int(time.time())+1000}))
    path=f"/api/v1/orders/{order['orderId']}/tracking-token"
    assert invoke(tracking.main,'DELETE',path,actor=OTHER_STORE)[0]==404
    assert invoke(tracking.main,'DELETE',path,actor=STORE)[0]==204
    assert call(order,public=True)[0]==404
    assert invoke(tracking.main,'GET',f"/api/v1/tracking/{order['trackingToken']}")[0]==404
    assert invoke(tracking.main,'DELETE',path,actor=STORE)[0]==204
    assert call(order,actor=STORE)[0]==200  # revoca enlace, no permisos del propietario


def test_redis_down_preserves_delivery_and_status_tracking(geo,monkeypatch):
    order,_=geo
    class Down:
        def __getattr__(self,name):
            def fail(*args,**kwargs): raise RedisConnectionError('caído')
            return fail
    monkeypatch.setitem(clients._SHARED,'redis',Down())
    assert call(order)[0]==503
    assert call(order,'POST',body=point())[0]==503
    assert invoke(tracking.main,'GET',f"/api/v1/tracking/{order['trackingToken']}")[0]==200
    assert act(order,'pickup',COURIER)[0]==200
    assert act(order,'deliver',COURIER)[0]==200


def test_pending_order_and_nonexistent_order(geo):
    pending = new_order('pending_geo')[1]
    assert call(pending, actor=STORE)[1]['freshness'] == 'UNAVAILABLE'
    assert call(pending, 'POST', body=point())[0] == 403
    missing = {**pending, 'orderId': 'missing'}
    assert call(missing, actor=STORE)[0] == 404


def test_simulation_and_gps_use_same_contract(geo):
    order, _ = geo
    assert call(order, 'POST', body=point(source='BROWSER_GPS'))[0] == 202
    assert call(order, public=True)[1]['location']['source'] == 'BROWSER_GPS'


def test_legacy_token_cannot_authorize_location(geo):
    order, _ = geo
    # Un ítem sin credencial nueva representa el modelo histórico; nunca gana permiso geográfico.
    adapter = clients.shared_adapter()
    adapter.client.delete_item(TableName=adapter.settings.table_name, Key=serialize(access_key(order['orderId'])))
    assert call(order, public=True)[0] == 404
    assert invoke(tracking.main, 'GET', f"/api/v1/tracking/{order['trackingToken']}")[0] == 200


def test_stop_rejects_inflight_sample_even_with_future_client_clock(geo):
    from lambdas.tracking.location_store import RedisLocationStore
    from lambdas.tracking.service import validate_point
    order, cache = geo
    store = RedisLocationStore(cache)
    started = time.time()
    sample = validate_point(point(10), started)
    store.stop(order['orderId'], started + .001)
    assert store.publish(order['orderId'], 'rep1', sample, started) == 0
    assert call(order, public=True)[1]['location'] is None
