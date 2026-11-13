"""Couriers: alta propia, habilitación administrativa, disponibilidad declarada (T6),
pedido activo e historial (CU02, CU06, CU09)."""
from lambdas.couriers.repository import CouriersRepository, courier_profile
from lambdas.identity.contracts import ActorContext, authorize
from lambdas.orders.service import load_order, order_view
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import page_dto
from lambdas.shared.storage.transactions import commit
from lambdas.stores.service import profile_name, require_zone

PHYSICAL = {"PK", "SK", "entityType", "schemaVersion"}


def courier_view(courier):
    return {name: courier[name] for name in ("courierId", "name", "zoneId", "enabled", "available",
                                             "createdAt", "updatedAt", "version")}


def history_view(view):
    return {name: view[name] for name in ("orderId", "storeId", "status", "createdAt", "updatedAt", "version")}


def _load(adapter, courier_id, *, missing):
    try:
        courier = CouriersRepository(adapter).get_profile(courier_id)
    except ValueError as exc:
        raise ValidationError("courierId inválido") from exc
    if courier is None:
        raise missing
    return courier


def _replace(adapter, courier, **changes):
    data = {k: v for k, v in courier.items() if k not in PHYSICAL}
    data.update(changes, updatedAt=max(clock.now(), courier["updatedAt"]), version=courier["version"] + 1)
    new = make_item("COURIER", **data)
    commit(adapter, [(CouriersRepository(adapter).build_put(new, expected_version=courier["version"]),
                      ConflictError("El perfil cambió; vuelve a intentarlo", "COURIER_CHANGED"))])
    return new


def register_courier(adapter, actor: ActorContext, *, name, zone_id):
    """Perfil propio, deshabilitado y no disponible hasta la aprobación de un ADMIN."""
    authorize(actor, "COURIER")
    repo = CouriersRepository(adapter)
    courier = courier_profile(courier_id=actor.courier_id, owner_id=actor.actor_id, zone_id=require_zone(zone_id),
                              name=profile_name(name), enabled=False, available=False, created_at=clock.now())
    commit(adapter, [(repo.build_put(courier),
                      ConflictError("Ya registraste tu perfil de repartidor", "COURIER_ALREADY_REGISTERED"))])
    return courier_view(courier)


def get_my_courier(adapter, actor: ActorContext):
    authorize(actor, "COURIER")
    return courier_view(_load(adapter, actor.courier_id, missing=NotFoundError(
        "Aún no registras tu perfil de repartidor", "COURIER_NOT_REGISTERED")))


def set_availability(adapter, actor: ActorContext, available):
    """T6: actualización condicional del perfil. Dejar de estar disponible no cancela el
    pedido activo; solo impide aceptar nuevos."""
    authorize(actor, "COURIER")
    if type(available) is not bool:
        raise ValidationError("available debe ser booleano")
    courier = _load(adapter, actor.courier_id, missing=NotFoundError(
        "Aún no registras tu perfil de repartidor", "COURIER_NOT_REGISTERED"))
    if available and not courier["enabled"]:
        raise ForbiddenError("Tu perfil aún no está habilitado", "COURIER_NOT_ENABLED")
    if courier["available"] == available:
        return courier_view(courier)
    return courier_view(_replace(adapter, courier, available=available))


def set_courier_enabled(adapter, actor: ActorContext, courier_id, enabled):
    authorize(actor, "ADMIN")
    if type(enabled) is not bool:
        raise ValidationError("enabled debe ser booleano")
    courier = _load(adapter, courier_id, missing=NotFoundError("Repartidor no encontrado", "COURIER_NOT_FOUND"))
    if courier["enabled"] == enabled:
        return courier_view(courier)
    changes = {"enabled": enabled}
    if not enabled:
        changes["available"] = False  # un perfil deshabilitado no puede seguir disponible
    return courier_view(_replace(adapter, courier, **changes))


def get_active_order(adapter, actor: ActorContext):
    """Lectura fuerte de COURIER#id / ACTIVE y del pedido correspondiente."""
    authorize(actor, "COURIER")
    active = CouriersRepository(adapter).get_active(actor.courier_id)
    if active is None:
        return None
    return order_view(load_order(adapter, active["orderId"]), detail=True)


def list_my_orders(adapter, actor: ActorContext, page):
    authorize(actor, "COURIER")
    repo = CouriersRepository(adapter)
    return page_dto(lambda: repo.list_orders(actor.courier_id, **page), history_view)
