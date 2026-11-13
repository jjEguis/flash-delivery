"""Tracking: seguimiento público por token, con respuesta mínima."""
from urllib.parse import unquote

from lambdas.orders.repository import OrdersRepository
from lambdas.shared.exceptions import NotFoundError, ValidationError
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter
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


ROUTES = {"GET /api/v1/tracking/{token}": track}
main = router(ROUTES)
