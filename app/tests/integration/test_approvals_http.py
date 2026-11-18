"""SPEC-10 por API Gateway real: auditoría y carrera suspensión/aceptación."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
import pytest
from tests.integration.test_api_flow import api, eventually

pytestmark = pytest.mark.integration


def prepare(api):
    run = uuid4().hex[:10]
    store, courier = 'as'+run, 'ac'+run
    admin = api.login('admin', 'ADMIN')
    st = api.login(store, 'STORE')
    co = api.login(courier, 'COURIER')
    assert api.call('POST', '/api/v1/stores', {'name':'Comercio aprobación','zoneId':'centro'}, st)[0] == 201
    assert api.call('POST', '/api/v1/couriers', {'name':'Repartidor aprobación','zoneId':'centro'}, co)[0] == 201
    return store,courier,admin,st,co


def test_approval_lists_audit_and_active_guard(api):
    store,courier,admin,st,co = prepare(api)
    path = f'/api/v1/admin/stores/{store}'
    for token, status in ((None,401),(st,403),(co,403)):
        assert api.call('GET','/api/v1/admin/stores',token=token)[0] == status
        assert api.call('GET',path+'/events',token=token)[0] == status
    pending = eventually(lambda: [p for p in api.call('GET','/api/v1/admin/stores?status=PENDING&limit=100',token=admin)[1]['items'] if p['storeId']==store])
    assert pending and pending[0]['approvalStatus']=='PENDING'
    change = {'enabled':True,'expectedVersion':1,'reason':'Verificación documental'}
    assert api.call('PATCH',path,change,admin)[0] == 200
    assert api.call('PATCH',path,change,admin)[1]['version'] == 2
    assert api.call('PATCH',path,{'enabled':False,'expectedVersion':1,'reason':'Desactualizado'},admin)[0] == 409
    audit = api.call('GET',path+'/events',token=admin)[1]['items']
    assert len(audit)==1 and audit[0]['reason']==change['reason'] and audit[0]['actorId']=='admin'
    cp = f'/api/v1/admin/couriers/{courier}'
    assert api.call('PATCH',cp,change,admin)[0] == 200
    assert api.call('PATCH','/api/v1/couriers/me/availability',{'available':True},co)[0] == 200
    status,order = api.call('POST','/api/v1/orders',{'pickupAddress':'Origen','dropoffAddress':'Destino','feeMinor':5000},st,key='create')
    assert status==201,order
    oid=order['orderId'];api.created['orders'].add(oid);api.track(store,'orders.create.v1','create')
    api.track(courier,'dispatch.accept.v1','accept')
    assert api.call('POST',f'/api/v1/orders/{oid}/accept',token=co,key='accept')[0] == 200
    version=api.call('GET',cp,token=admin)[1]['version']
    failure=api.call('PATCH',cp,{'enabled':False,'expectedVersion':version,'reason':'Pausa solicitada'},admin)
    assert failure[0]==409 and failure[1]['error']['code']=='COURIER_HAS_ACTIVE_ORDER', failure
    assert len(api.call('GET',cp+'/events',token=admin)[1]['items'])==1
    assert api.call('GET',cp,token=admin)[1]['activeOrderId']==oid
    for action in ('pickup','deliver'):
        api.track(courier,f'dispatch.{action}.v1',action)
        assert api.call('POST',f'/api/v1/orders/{oid}/{action}',token=co,key=action)[0]==200
    assert api.call('PATCH',cp,{'enabled':False,'expectedVersion':version,'reason':'Pausa solicitada'},admin)[0]==200
    current=api.call('GET',cp,token=admin)[1]
    assert not current['enabled'] and not current['available'] and current['activeOrderId'] is None
    first=api.call('GET',cp+'/events?limit=1',token=admin)[1]
    assert first['items'][0]['toStatus']=='SUSPENDED' and first['nextCursor']
    from urllib.parse import quote
    assert api.call('GET',cp+'/events?limit=1&cursor='+quote(first['nextCursor']),token=admin)[1]['items'][0]['toStatus']=='ENABLED'


@pytest.mark.parametrize('attempt',range(3))
def test_accept_and_suspend_cannot_both_win(api,attempt):
    store,courier,admin,st,co = prepare(api)
    for kind,identity in (('stores',store),('couriers',courier)):
        assert api.call('PATCH',f'/api/v1/admin/{kind}/{identity}',{'enabled':True},admin)[0]==200
    assert api.call('PATCH','/api/v1/couriers/me/availability',{'available':True},co)[0]==200
    status,order=api.call('POST','/api/v1/orders',{'pickupAddress':'Carrera','dropoffAddress':'Destino','feeMinor':1000},st,key='race_create')
    assert status==201,order
    oid=order['orderId'];api.created['orders'].add(oid);api.track(store,'orders.create.v1','race_create');api.track(courier,'dispatch.accept.v1','race_accept')
    gate=Barrier(2)
    def accept():
        gate.wait();return api.call('POST',f'/api/v1/orders/{oid}/accept',token=co,key='race_accept')
    def suspend():
        gate.wait();return api.call('PATCH',f'/api/v1/admin/couriers/{courier}',{'enabled':False,'reason':'Pausa concurrente'},admin)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(accept);s=pool.submit(suspend);accepted,suspended=a.result(),s.result()
    assert sum(result[0]==200 for result in (accepted,suspended))==1, (accepted,suspended)
    assert accepted[0] in (200,403,409) and suspended[0] in (200,409)
    profile=api.call('GET',f'/api/v1/admin/couriers/{courier}',token=admin)[1]
    assert not (profile['activeOrderId'] and not profile['enabled']),profile
    audit=api.call('GET',f'/api/v1/admin/couriers/{courier}/events',token=admin)[1]['items']
    assert len(audit)==(2 if suspended[0]==200 else 1)
