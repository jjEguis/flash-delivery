"""Stores: zonas, perfil del comercio y habilitación administrativa."""
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter
from lambdas.stores import service


def list_zones(request):
    return 200, {"items": service.zones()}


def register(request):
    data = request.json()
    return 201, service.register_store(shared_adapter(), request.actor, name=data.get("name"),
                                       zone_id=data.get("zoneId"))


def me(request):
    return 200, service.get_my_store(shared_adapter(), request.actor)


def set_enabled(request):
    return 200, service.set_store_enabled(shared_adapter(), request.actor, request.path_params["storeId"],
                                          request.json().get("enabled"))


ROUTES = {
    "GET /api/v1/zones": list_zones,
    "POST /api/v1/stores": register,
    "GET /api/v1/stores/me": me,
    "PATCH /api/v1/admin/stores/{storeId}": set_enabled,
}
main = router(ROUTES)
