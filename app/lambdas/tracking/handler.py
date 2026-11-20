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
    from lambdas.tracking.routes import advance_safely
    adapter, client = shared_adapter(), shared_redis()
    return 202, service.publish(adapter, RedisLocationStore(client), request.actor,
                                request.path_params['orderId'], request.json(),
                                on_accepted=lambda order, point: advance_safely(adapter, client, order, point))


def latest(request):
    return 200, service.latest(shared_adapter(), RedisLocationStore(shared_redis()), actor=request.actor,
                               order_id=request.path_params['orderId'])


def public_latest(request):
    return 200, service.latest(shared_adapter(), RedisLocationStore(shared_redis()),
                               token=unquote(request.path_params['token']))


def stop(request):
    from lambdas.tracking.routes import clear_routes
    client = shared_redis()
    service.stop(shared_adapter(), RedisLocationStore(client), request.actor, request.path_params['orderId'])
    service._dependency(lambda: clear_routes(client, request.path_params['orderId']))
    return 204, None


def revoke(request):
    service.revoke(shared_adapter(), request.actor, request.path_params['orderId'])
    return 204, None


def route(request):
    from lambdas.tracking.routes import get_route
    return 200, get_route(shared_adapter(), shared_redis(), actor=request.actor, order_id=request.path_params["orderId"])


def public_route(request):
    from lambdas.tracking.routes import get_route
    return 200, get_route(shared_adapter(), shared_redis(), token=unquote(request.path_params["token"]))


ROUTES = {
    "GET /api/v1/tracking/{token}": track,
    "POST /api/v1/orders/{orderId}/location": publish,
    "GET /api/v1/orders/{orderId}/location": latest,
    "DELETE /api/v1/orders/{orderId}/location": stop,
    "GET /api/v1/tracking/{token}/location": public_latest,
    "DELETE /api/v1/orders/{orderId}/tracking-token": revoke,
    "GET /api/v1/orders/{orderId}/route": route,
    "GET /api/v1/tracking/{token}/route": public_route,
}
main = router(ROUTES)
