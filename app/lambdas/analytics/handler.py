"""Analytics: estadística mensual del comercio (Cache-Aside en Redis)."""
from lambdas.analytics.service import get_month_stats
from lambdas.shared import clock
from lambdas.shared.http import router
from lambdas.shared.infrastructure.clients import shared_adapter, shared_redis


def stats(request):
    month = request.query.get("month") or clock.month_of(clock.now())
    return 200, get_month_stats(shared_adapter(), shared_redis(), request.actor, month)


ROUTES = {"GET /api/v1/stores/me/stats": stats}
main = router(ROUTES)
