"""Tracking: seguimiento público por token, con respuesta mínima."""
from urllib.parse import unquote

from lambdas.orders.repository import OrdersRepository
from lambdas.shared.exceptions import NotFoundError, ValidationError
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter, shared_redis
from lambdas.tracking import service
from lambdas.tracking.location_store import RedisLocationStore
from lambdas.tracking.repository import TrackingRepository


def track(request):
    page = request.page()
    try:
        result = TrackingRepository(OrdersRepository(shared_adapter())).get_tracking(
            unquote(request.path_params["token"]), **page)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if result is None:
        # Mismo error para token mal formado, inexistente o con secreto incorrecto.
        raise NotFoundError("Seguimiento no encontrado", "TRACKING_NOT_FOUND")
    return 200, result


def publish(request):
    return 202, service.publish(shared_adapter(), RedisLocationStore(shared_redis()), request.actor,
                                request.path_params['orderId'], request.json())


def latest(request):
    return 200, service.latest(shared_adapter(), RedisLocationStore(shared_redis()), actor=request.actor,
                               order_id=request.path_params['orderId'])


def public_latest(request):
    return 200, service.latest(shared_adapter(), RedisLocationStore(shared_redis()),
                               token=unquote(request.path_params['token']))


def stop(request):
    service.stop(shared_adapter(), RedisLocationStore(shared_redis()), request.actor, request.path_params['orderId'])
    return 204, None


def revoke(request):
    service.revoke(shared_adapter(), request.actor, request.path_params['orderId'])
    return 204, None


ROUTES = {
    "GET /api/v1/tracking/{token}": track,
    "POST /api/v1/orders/{orderId}/location": publish,
    "GET /api/v1/orders/{orderId}/location": latest,
    "DELETE /api/v1/orders/{orderId}/location": stop,
    "GET /api/v1/tracking/{token}/location": public_latest,
    "DELETE /api/v1/orders/{orderId}/tracking-token": revoke,
}
main = router(ROUTES)
