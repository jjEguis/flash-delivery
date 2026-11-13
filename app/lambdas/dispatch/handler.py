"""Dispatch: aceptar, recoger, entregar, cancelar y marcar fallido."""
from lambdas.dispatch import service
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter, shared_redis


def _transition(command, **extra):
    def handle(request):
        return 200, command(shared_adapter(), request.actor, request.path_params["orderId"],
                            request_id=request.idempotency_key, **{k: v() for k, v in extra.items()})
    return handle


ROUTES = {
    "POST /api/v1/orders/{orderId}/accept": _transition(service.accept_order),
    "POST /api/v1/orders/{orderId}/pickup": _transition(service.pick_up_order),
    "POST /api/v1/orders/{orderId}/deliver": _transition(service.deliver_order, cache=shared_redis),
    "POST /api/v1/orders/{orderId}/cancel": _transition(service.cancel_order),
    "POST /api/v1/orders/{orderId}/fail": _transition(service.fail_order),
}
main = router(ROUTES)
