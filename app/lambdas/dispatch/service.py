"""Dispatch: aceptación competitiva y transiciones críticas del pedido.

Cada comando lee con consistencia fuerte, valida reglas para responder errores claros y
confirma todo en un único TransactWriteItems. Las condiciones de la transacción son las
que realmente garantizan las invariantes ante carreras:

- un repartidor por pedido: META se sustituye condicionada a la versión leída (PENDING);
- un pedido activo por repartidor: COURIER#id / ACTIVE se crea con attribute_not_exists;
- las proyecciones y el evento se confirman o se descartan junto con META.
"""
import logging

from lambdas.analytics.repository import AnalyticsRepository
from lambdas.couriers.repository import CouriersRepository, active_assignment, courier_order_view
from lambdas.identity.contracts import ActorContext, authorize
from lambdas.orders.service import build_transition, load_order, order_view
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, ForbiddenError, NotFoundError
from lambdas.shared.storage.transactions import run_command

logger = logging.getLogger(__name__)


def _courier(couriers, courier_id):
    courier = couriers.get_profile(courier_id)
    if courier is None:
        raise NotFoundError("Primero registra tu perfil de repartidor", "COURIER_NOT_REGISTERED")
    if not courier["enabled"]:
        raise ForbiddenError("Tu perfil de repartidor aún no está habilitado", "COURIER_NOT_ENABLED")
    return courier


def _assigned_to(order, courier_id):
    if order.get("courierId") != courier_id:
        # Para otro repartidor el pedido no es visible.
        raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")


def _execute(adapter, actor, operation, order_id, request_id, build, cache=None, after=None):
    now = clock.now()
    run_command(adapter, actor_id=actor.actor_id, operation=operation, request_id=request_id,
                payload={"orderId": order_id}, build=lambda: build(now), now=now)
    order = load_order(adapter, order_id)
    if after:
        after(order, cache)
    return order_view(order, detail=True)


def accept_order(adapter, actor: ActorContext, order_id, *, request_id):
    """T2: un solo ganador entre repartidores concurrentes; los demás reciben 409."""
    authorize(actor, "COURIER")
    couriers = CouriersRepository(adapter)

    def build(now):
        courier = _courier(couriers, actor.courier_id)
        if not courier["available"]:
            raise ConflictError("Activa tu disponibilidad para aceptar pedidos", "COURIER_NOT_AVAILABLE")
        if couriers.get_active(actor.courier_id) is not None:
            raise ConflictError("Ya tienes un pedido activo", "COURIER_HAS_ACTIVE_ORDER")
        order = load_order(adapter, order_id)
        if order["zoneId"] != courier["zoneId"]:
            raise ForbiddenError("El pedido pertenece a otra zona", "ZONE_MISMATCH")
        if order["status"] != "PENDING":
            raise ConflictError("Otro repartidor ya aceptó este pedido", "ORDER_ALREADY_ASSIGNED")
        new, pairs = build_transition(adapter, order, "ASSIGNED", now, courier_id=actor.courier_id)
        taken = ConflictError("Otro repartidor ya aceptó este pedido", "ORDER_ALREADY_ASSIGNED")
        pairs[0], pairs[2] = (pairs[0][0], taken), (pairs[2][0], taken)
        return pairs + [
            (couriers.build_eligible_condition(actor.courier_id, courier["zoneId"], courier["version"]),
             ConflictError("Tu perfil cambió mientras aceptabas; vuelve a intentarlo", "COURIER_CHANGED")),
            (couriers.build_put(active_assignment(actor.courier_id, order_id, new["updatedAt"])),
             ConflictError("Ya tienes un pedido activo", "COURIER_HAS_ACTIVE_ORDER")),
            (couriers.build_put(courier_order_view(new)), None),
        ], {"orderId": order_id, "status": "ASSIGNED"}

    return _execute(adapter, actor, "dispatch.accept.v1", order_id, request_id, build)


def pick_up_order(adapter, actor: ActorContext, order_id, *, request_id):
    """T3: solo el repartidor asignado, desde ASSIGNED."""
    authorize(actor, "COURIER")
    couriers = CouriersRepository(adapter)

    def build(now):
        order = load_order(adapter, order_id)
        _assigned_to(order, actor.courier_id)
        new, pairs = build_transition(adapter, order, "PICKED_UP", now)
        return pairs + [(couriers.build_put(courier_order_view(new), expected_version=order["version"]), None)], \
            {"orderId": order_id, "status": "PICKED_UP"}

    return _execute(adapter, actor, "dispatch.pickup.v1", order_id, request_id, build)


def _invalidate_stats(order, cache):
    if cache is None:
        return
    from lambdas.analytics.service import invalidate_month
    invalidate_month(cache, order["storeId"], clock.month_of(order["updatedAt"]))


def deliver_order(adapter, actor: ActorContext, order_id, *, request_id, cache=None):
    """T4: entrega, libera ACTIVE del pedido esperado y suma la estadística una sola vez."""
    authorize(actor, "COURIER")
    couriers, analytics = CouriersRepository(adapter), AnalyticsRepository(adapter)

    def build(now):
        order = load_order(adapter, order_id)
        _assigned_to(order, actor.courier_id)
        new, pairs = build_transition(adapter, order, "DELIVERED", now)
        return pairs + [
            (couriers.build_put(courier_order_view(new), expected_version=order["version"]), None),
            (couriers.build_release_active(actor.courier_id, order_id),
             ConflictError("La asignación activa no corresponde a este pedido", "ACTIVE_MISMATCH")),
            (analytics.build_increment(order["storeId"], clock.month_of(new["updatedAt"]),
                                       order["feeMinor"], new["updatedAt"]), None),
        ], {"orderId": order_id, "status": "DELIVERED"}

    return _execute(adapter, actor, "dispatch.deliver.v1", order_id, request_id, build,
                    cache=cache, after=_invalidate_stats)


def _release_assignment(couriers, order, new):
    """Acciones para retirar la asignación del repartidor cuando el pedido termina sin entrega."""
    courier_id = order.get("courierId")
    if not courier_id:
        return []
    return [(couriers.build_put(courier_order_view(new), expected_version=order["version"]), None),
            (couriers.build_release_active(courier_id, order["orderId"]),
             ConflictError("La asignación activa no corresponde a este pedido", "ACTIVE_MISMATCH"))]


def cancel_order(adapter, actor: ActorContext, order_id, *, request_id):
    """T5: el comercio propietario cancela en PENDING o ASSIGNED; nunca tras la recogida."""
    authorize(actor, "STORE")
    couriers = CouriersRepository(adapter)

    def build(now):
        order = load_order(adapter, order_id)
        if order["storeId"] != actor.store_id:
            raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")
        if order["status"] not in {"PENDING", "ASSIGNED"}:
            raise ConflictError("Solo se cancelan pedidos pendientes o asignados", "INVALID_TRANSITION")
        new, pairs = build_transition(adapter, order, "CANCELLED", now)
        return pairs + _release_assignment(couriers, order, new), {"orderId": order_id, "status": "CANCELLED"}

    return _execute(adapter, actor, "dispatch.cancel.v1", order_id, request_id, build)


def fail_order(adapter, actor: ActorContext, order_id, *, request_id):
    """Procedimiento excepcional: solo ADMIN marca FAILED un pedido recogido."""
    authorize(actor, "ADMIN")
    couriers = CouriersRepository(adapter)

    def build(now):
        order = load_order(adapter, order_id)
        new, pairs = build_transition(adapter, order, "FAILED", now)
        return pairs + _release_assignment(couriers, order, new), {"orderId": order_id, "status": "FAILED"}

    return _execute(adapter, actor, "dispatch.fail.v1", order_id, request_id, build)
