"""Couriers: perfil, disponibilidad declarada, pedido activo, historial y habilitación."""
import logging

from lambdas.couriers import service
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter, shared_redis

logger = logging.getLogger(__name__)


def register(request):
    data = request.json()
    return 201, service.register_courier(shared_adapter(), request.actor, name=data.get("name"),
                                         zone_id=data.get("zoneId"))


def me(request):
    return 200, service.get_my_courier(shared_adapter(), request.actor)


def _leave_presence(courier):
    """Tras confirmar en DynamoDB, retirar la presencia efímera (Redis es derivado)."""
    try:
        from lambdas.availability.service import go_offline
        go_offline(shared_redis(), courier["courierId"], courier["zoneId"])
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - un fallo de Redis no revierte el commit
        logger.warning("No se pudo retirar la presencia en Redis; expirará por TTL")


def availability(request):
    courier = service.set_availability(shared_adapter(), request.actor, request.json().get("available"))
    if not courier["available"]:
        _leave_presence(courier)
    return 200, courier


def active(request):
    return 200, {"order": service.get_active_order(shared_adapter(), request.actor)}


def history(request):
    return 200, service.list_my_orders(shared_adapter(), request.actor, request.page())


def set_enabled(request):
    courier = service.set_courier_enabled(shared_adapter(), request.actor, request.path_params["courierId"],
                                          request.json().get("enabled"))
    if not courier["enabled"]:
        _leave_presence(courier)
    return 200, courier


ROUTES = {
    "POST /api/v1/couriers": register,
    "GET /api/v1/couriers/me": me,
    "PATCH /api/v1/couriers/me/availability": availability,
    "GET /api/v1/couriers/me/active": active,
    "GET /api/v1/couriers/me/orders": history,
    "PATCH /api/v1/admin/couriers/{courierId}": set_enabled,
}
main = router(ROUTES)
