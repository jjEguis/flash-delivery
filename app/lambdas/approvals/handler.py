"""Consultas administrativas; las mutaciones conservan sus endpoints previos."""
from lambdas.approvals import service
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter


def listing(kind):
    return lambda request: (200, service.listing(shared_adapter(), request.actor, kind,
                                                request.query.get('status','PENDING'), request.page()))


def detail(kind, parameter):
    return lambda request: (200, service.detail(shared_adapter(), request.actor, kind, request.path_params[parameter]))


def events(kind, parameter):
    return lambda request: (200, service.events(shared_adapter(), request.actor, kind, request.path_params[parameter], request.page()))


ROUTES = {
    'GET /api/v1/admin/stores': listing('STORE'),
    'GET /api/v1/admin/couriers': listing('COURIER'),
    'GET /api/v1/admin/stores/{storeId}': detail('STORE','storeId'),
    'GET /api/v1/admin/couriers/{courierId}': detail('COURIER','courierId'),
    'GET /api/v1/admin/stores/{storeId}/events': events('STORE','storeId'),
    'GET /api/v1/admin/couriers/{courierId}/events': events('COURIER','courierId'),
}
main = router(ROUTES)
