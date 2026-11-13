"""Orders: crear, consultar y listar pedidos."""
from lambdas.couriers.service import get_my_courier
from lambdas.identity.contracts import authorize
from lambdas.orders import service
from lambdas.shared.exceptions import ForbiddenError, ValidationError
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter


def create(request):
    data = request.json()
    return 201, service.create_order(shared_adapter(), request.actor, request_id=request.idempotency_key,
                                     pickup_address=data.get("pickupAddress"),
                                     dropoff_address=data.get("dropoffAddress"), fee_minor=data.get("feeMinor"))


def available(request):
    """Ofertas abiertas: solo repartidores habilitados y de la zona consultada."""
    actor = authorize(request.actor, "COURIER", "ADMIN")
    zone_id = request.query.get("zoneId")
    if not zone_id:
        raise ValidationError("zoneId es obligatorio")
    if actor.role == "COURIER":
        courier = get_my_courier(shared_adapter(), actor)
        if not courier["enabled"]:
            raise ForbiddenError("Tu perfil aún no está habilitado", "COURIER_NOT_ENABLED")
        if courier["zoneId"] != zone_id:
            raise ForbiddenError("Solo puedes ver pedidos de tu zona", "ZONE_MISMATCH")
    return 200, service.list_open_orders(shared_adapter(), zone_id, request.page())


def detail(request):
    return 200, service.get_order(shared_adapter(), request.actor, request.path_params["orderId"])


def events(request):
    return 200, service.list_events(shared_adapter(), request.actor, request.path_params["orderId"], request.page())


def store_orders(request):
    return 200, service.list_store_orders(shared_adapter(), request.actor, request.page(),
                                          status=request.query.get("status"))


ROUTES = {
    "POST /api/v1/orders": create,
    "GET /api/v1/orders/available": available,
    "GET /api/v1/orders/{orderId}": detail,
    "GET /api/v1/orders/{orderId}/events": events,
    "GET /api/v1/stores/me/orders": store_orders,
}
main = router(ROUTES)
