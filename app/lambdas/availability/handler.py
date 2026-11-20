"""Availability: heartbeat, salida y presencia por zona."""
from lambdas.availability import service
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter, shared_redis


def beat(request):
    return 200, service.heartbeat(shared_adapter(), shared_redis(), request.actor)


def leave(request):
    service.leave(shared_adapter(), shared_redis(), request.actor)
    return 204, None


def present(request):
    return 200, service.list_present(shared_adapter(), shared_redis(), request.actor,
                                     request.path_params["zoneId"], request.page())


ROUTES = {
    "POST /api/v1/couriers/me/heartbeat": beat,
    "DELETE /api/v1/couriers/me/heartbeat": leave,
    "GET /api/v1/zones/{zoneId}/couriers": present,
}
main = router(ROUTES)
