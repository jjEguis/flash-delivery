"""Casos de uso de Orders: crear pedido (T1), consultar y construir transiciones.

Orders es dueño del estado del pedido. Dispatch compone las transiciones que aquí se
construyen con las piezas de Couriers y Analytics en un único commit.
"""
from lambdas.identity.contracts import ActorContext, authorize
from lambdas.orders.repository import OrdersRepository, order_event, order_meta, store_status_view
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.transactions import run_command
from lambdas.stores.repository import StoresRepository
from lambdas.tracking.tokens import issue_token

CURRENCY = "COP"
MAX_FEE_MINOR = 100_000_000
TRANSITIONS = {
    ("PENDING", "ASSIGNED"), ("ASSIGNED", "PICKED_UP"), ("PICKED_UP", "DELIVERED"),
    ("PENDING", "CANCELLED"), ("ASSIGNED", "CANCELLED"), ("PICKED_UP", "FAILED"),
}
EVENT_FOR = {"ASSIGNED": "ASSIGNED", "PICKED_UP": "PICKED_UP", "DELIVERED": "DELIVERED",
             "CANCELLED": "CANCELLED", "FAILED": "FAILED"}
PHYSICAL = {"PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "entityType", "schemaVersion"}


def _text(value, field, maximum=300):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValidationError(f"{field} debe ser texto de 1 a {maximum} caracteres")
    return value.strip()


def _fee(value):
    if type(value) is not int or not 0 < value <= MAX_FEE_MINOR:
        raise ValidationError(f"feeMinor debe ser un entero entre 1 y {MAX_FEE_MINOR}")
    return value


def order_view(order, *, detail):
    """DTO sin claves físicas ni hashes. Las direcciones solo van en el detalle."""
    view = {name: order[name] for name in ("orderId", "storeId", "zoneId", "status", "createdAt",
                                           "updatedAt", "version") if name in order}
    for name in ("feeMinor", "currency", "courierId", "pickupAddress"):
        if name in order:
            view[name] = order[name]
    if detail and "dropoffAddress" in order:
        view["dropoffAddress"] = order["dropoffAddress"]
    return view


def can_read(actor, order):
    return (actor.role == "ADMIN" or (actor.role == "STORE" and order["storeId"] == actor.store_id)
            or (actor.role == "COURIER" and order.get("courierId") == actor.courier_id))


def load_order(adapter, order_id):
    try:
        order = OrdersRepository(adapter).get_order(order_id)
    except ValueError as exc:
        raise ValidationError("orderId inválido") from exc
    if order is None:
        raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")
    return order


def get_order(adapter, actor: ActorContext, order_id):
    order = load_order(adapter, order_id)
    if not can_read(actor, order):
        # No revelar la existencia de pedidos ajenos.
        raise NotFoundError("Pedido no encontrado", "ORDER_NOT_FOUND")
    return order_view(order, detail=True)


def create_order(adapter, actor: ActorContext, *, request_id, pickup_address, dropoff_address, fee_minor):
    """T1: comercio habilitado + META PENDING + evento CREATED + vista de estado + idempotencia."""
    authorize(actor, "STORE")
    payload = {"pickupAddress": _text(pickup_address, "pickupAddress"),
               "dropoffAddress": _text(dropoff_address, "dropoffAddress"), "feeMinor": _fee(fee_minor)}
    orders, stores = OrdersRepository(adapter), StoresRepository(adapter)
    now = clock.now()

    def build():
        store = stores.get_profile(actor.store_id)
        if store is None:
            raise NotFoundError("Primero registra tu comercio", "STORE_NOT_REGISTERED")
        if not store["enabled"]:
            raise ForbiddenError("Tu comercio aún no está habilitado", "STORE_NOT_ENABLED")
        order_id = clock.new_id("o_")
        _, token_hash = issue_token(order_id)
        order = order_meta(order_id=order_id, store_id=store["storeId"], zone_id=store["zoneId"],
                           created_at=now, pickup_address=payload["pickupAddress"],
                           dropoff_address=payload["dropoffAddress"], fee_minor=payload["feeMinor"],
                           currency=CURRENCY, tracking_token_hash=token_hash)
        changed = ForbiddenError("Tu comercio cambió o fue deshabilitado", "STORE_NOT_ENABLED")
        return [(stores.build_enabled_condition(store["storeId"], store["version"]), changed),
                (orders.build_put(order), None),
                (orders.build_put(order_event(order_id, clock.new_id("e_"), "CREATED", now)), None),
                (orders.build_put(store_status_view(order)), None)], {"orderId": order_id}

    result = run_command(adapter, actor_id=actor.actor_id, operation="orders.create.v1",
                         request_id=request_id, payload=payload, build=build, now=now)
    order = load_order(adapter, result["orderId"])
    token, _ = issue_token(order["orderId"])
    return {**order_view(order, detail=True), "trackingToken": token}


def fields(item):
    return {name: value for name, value in item.items() if name not in PHYSICAL}


def build_transition(adapter, order, status, now, *, courier_id=None):
    """Nuevo META + evento + vista de estado del comercio, condicionados a la versión leída.

    Devuelve (pedido nuevo, pares acción/error). La sustitución completa de META retira
    las claves GSI2 de zona al salir de PENDING.
    """
    if (order["status"], status) not in TRANSITIONS:
        raise ConflictError(f"El pedido está {order['status']} y no puede pasar a {status}",
                            "INVALID_TRANSITION")
    data = fields(order)
    data.update(status=status, updatedAt=max(now, order["updatedAt"]), version=order["version"] + 1)
    if courier_id is not None:
        data["courierId"] = courier_id
    new = make_item("ORDER", **data)
    repo = OrdersRepository(adapter)
    changed = ConflictError("El pedido cambió mientras se procesaba", "ORDER_CHANGED")
    return new, [(repo.build_put(new, expected_version=order["version"]), changed),
                 (repo.build_put(order_event(order["orderId"], clock.new_id("e_"), EVENT_FOR[status],
                                             new["updatedAt"])), None),
                 (repo.build_put(store_status_view(new), expected_version=order["version"]), changed)]
