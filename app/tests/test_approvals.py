"""SPEC-10: bandeja, permisos, auditoría, versiones y guard transaccional."""
from copy import deepcopy
import pytest
from lambdas.approvals import handler as approvals
from lambdas.stores import handler as stores
from lambdas.couriers import handler as couriers
from lambdas.dispatch import handler as dispatch
from lambdas.shared.infrastructure import clients
from lambdas.shared.storage.model import deserialize,serialize,profile_status
from lambdas.shared.storage import keys
from scripts.backfill_approvals import migrate
from tests.http_helpers import invoke
from tests.test_http_base_flow import api, STORE,COURIER,ADMIN,enabled_store,enabled_courier,new_order


def get(kind='stores',tail='',actor=ADMIN,query=None):
    return invoke(approvals.main,'GET',f'/api/v1/admin/{kind}'+tail,actor=actor,query=query or {})


def patch(kind,identity,enabled,**extra):
    return invoke(stores.main if kind=='stores' else couriers.main,'PATCH',f'/api/v1/admin/{kind}/{identity}',actor=ADMIN,body={'enabled':enabled,**extra})


def test_list_permissions_paging_and_cursor_scope(api,monkeypatch):
    for i in range(3):
        assert invoke(stores.main,'POST','/api/v1/stores',actor=(f's{i}','STORE'),body={'name':f'Tienda {i}','zoneId':'centro'})[0]==201
    monkeypatch.setattr(clients.shared_adapter().client,'scan',lambda **kw:pytest.fail('Scan operativo'))
    assert get(actor=None)[0]==401
    assert get(actor=STORE)[0]==403 and get(actor=COURIER)[0]==403
    first=get(query={'limit':'1'})[1]
    assert len(first['items'])==1 and first['nextCursor']
    second=get(query={'limit':'1','cursor':first['nextCursor']})[1]
    assert second['items'][0]['storeId']!=first['items'][0]['storeId']
    assert get(query={'status':'ENABLED','cursor':first['nextCursor']})[0]==400
    assert get('couriers',query={'cursor':first['nextCursor']})[0]==400
    assert get(query={'status':'INVALID'})[0]==400
    assert all('PK' not in row and 'ownerId' not in row for row in first['items'])


def test_change_audit_noop_and_versions(api):
    invoke(stores.main,'POST','/api/v1/stores',actor=STORE,body={'name':'Tienda','zoneId':'centro'})
    status,enabled=patch('stores',STORE[0],True,expectedVersion=1,reason='Verificado')
    assert status==200 and enabled['approvalStatus']=='ENABLED' and enabled['version']==2
    status,again=patch('stores',STORE[0],True,expectedVersion=1,reason='Verificado')
    assert status==200 and again['version']==2
    audit=get(tail=f'/{STORE[0]}/events')[1]['items']
    assert len(audit)==1 and audit[0]['actorId']=='admin' and audit[0]['reason']=='Verificado'
    assert audit[0]['fromStatus']=='PENDING' and audit[0]['toStatus']=='ENABLED'
    assert patch('stores',STORE[0],False,expectedVersion=1,reason='Suspender')[0]==409
    assert patch('stores',STORE[0],False,expectedVersion=2,reason='Solicitud del titular')[0]==200
    assert get(query={'status':'SUSPENDED'})[1]['items'][0]['storeId']==STORE[0]
    assert len(get(tail=f'/{STORE[0]}/events')[1]['items'])==2
    assert get(tail=f'/{STORE[0]}',actor=COURIER)[0]==403
    assert get(tail='/missing')[0]==404
    assert get(tail=f'/{STORE[0]}/events',query={'limit':'1'})[1]['nextCursor']
    for body in ({'expectedVersion':True},{'expectedVersion':0},{'reason':' '},{'reason':42}):
        assert patch('stores',STORE[0],True,**body)[0]==400


def test_pending_can_be_rejected_and_reactivated(api):
    invoke(stores.main,'POST','/api/v1/stores',actor=STORE,body={'name':'Tienda','zoneId':'centro'})
    assert patch('stores',STORE[0],False,reason='Registro incompleto')[1]['approvalStatus']=='SUSPENDED'
    assert get()[1]['items']==[]
    assert patch('stores',STORE[0],True)[1]['approvalStatus']=='ENABLED'  # cliente anterior


def test_active_assignment_blocks_suspension_atomically(api):
    enabled_store();enabled_courier();order=new_order()[1]
    path=f"/api/v1/orders/{order['orderId']}"
    assert invoke(dispatch.main,'POST',path+'/accept',actor=COURIER,key='accept')[0]==200
    detail=get('couriers',f'/{COURIER[0]}')[1]
    assert detail['activeOrderId']==order['orderId']
    before=len(get('couriers',f'/{COURIER[0]}/events')[1]['items'])
    result=patch('couriers',COURIER[0],False,reason='Suspensión')
    assert result[0]==409 and result[1]['error']['code']=='COURIER_HAS_ACTIVE_ORDER'
    assert get('couriers',f'/{COURIER[0]}')[1]['enabled'] is True
    assert len(get('couriers',f'/{COURIER[0]}/events')[1]['items'])==before
    for action in ['pickup','deliver']:
        assert invoke(dispatch.main,'POST',path+'/'+action,actor=COURIER,key=action)[0]==200
    assert patch('couriers',COURIER[0],False)[1]['available'] is False
    assert invoke(couriers.main,'PATCH','/api/v1/couriers/me/availability',actor=COURIER,body={'available':True})[0]==403


def test_backfill_preserves_state_attributes_and_is_repeatable(api):
    enabled_store();adapter=clients.shared_adapter()
    key=keys.profile(keys.store(STORE[0]));raw=adapter.get_item(Key=serialize(key))['Item'];old=deserialize(raw)
    for name in ['approvalStatus','GSI2PK','GSI2SK']:old.pop(name)
    adapter.put_item(Item=serialize(old))
    assert get(query={'status':'ENABLED'})[1]['items']==[]
    assert migrate(adapter,dry_run=True)['updated']==1
    assert 'approvalStatus' not in deserialize(adapter.get_item(Key=serialize(key))['Item'])
    assert migrate(adapter)['updated']==1
    new=deserialize(adapter.get_item(Key=serialize(key))['Item'])
    assert new['version']==old['version'] and new['enabled']==old['enabled'] and new['createdAt']==old['createdAt']
    assert get(query={'status':'ENABLED'})[1]['items'][0]['storeId']==STORE[0]
    assert migrate(adapter)['updated']==0


def test_backfill_skips_concurrent_change(api,monkeypatch):
    enabled_store();adapter=clients.shared_adapter();key=keys.profile(keys.store(STORE[0]))
    old=deserialize(adapter.get_item(Key=serialize(key))['Item'])
    for name in ['approvalStatus','GSI2PK','GSI2SK']:old.pop(name)
    adapter.put_item(Item=serialize(old));update=adapter.update_item
    def race(**kwargs):
        latest=deepcopy(old);latest.update(version=old['version']+1,enabled=False)
        adapter.put_item(Item=serialize(latest));return update(**kwargs)
    monkeypatch.setattr(adapter,'update_item',race)
    assert migrate(adapter)['concurrent']==1
    latest=deserialize(adapter.get_item(Key=serialize(key))['Item'])
    assert latest['enabled'] is False and latest['version']==old['version']+1


def test_stale_gsi_result_does_not_show_old_approval(api,monkeypatch):
    from lambdas.approvals.repository import ApprovalsRepository
    from lambdas.shared.storage.repository import Page
    from lambdas.stores.repository import StoresRepository
    invoke(stores.main,'POST','/api/v1/stores',actor=STORE,body={'name':'Tienda','zoneId':'centro'})
    old=StoresRepository(clients.shared_adapter()).get_profile(STORE[0])
    assert patch('stores',STORE[0],True)[0]==200
    monkeypatch.setattr(ApprovalsRepository,'list_profiles',lambda *args,**kwargs:Page([old],'next-page'))
    result=get()[1]
    assert result=={'items':[],'nextCursor':'next-page'}


def test_failed_transaction_does_not_leave_profile_or_audit(api,monkeypatch):
    from botocore.exceptions import ClientError
    from lambdas.approvals.repository import ApprovalsRepository
    from lambdas.stores.repository import StoresRepository
    invoke(stores.main,'POST','/api/v1/stores',actor=STORE,body={'name':'Tienda','zoneId':'centro'})
    adapter=clients.shared_adapter()
    def fail(*args,**kwargs):
        raise ClientError({'Error':{'Code':'TransactionCanceledException'},'CancellationReasons':[{'Code':'ConditionalCheckFailed'},{'Code':'None'}]},'TransactWriteItems')
    monkeypatch.setattr(adapter,'transact_write_items',fail)
    assert patch('stores',STORE[0],True,expectedVersion=1,reason='No se debe guardar')[0]==409
    profile=StoresRepository(adapter).get_profile(STORE[0])
    assert profile['version']==1 and profile['approvalStatus']=='PENDING'
    assert ApprovalsRepository(adapter).events('STORE',STORE[0]).items==[]
