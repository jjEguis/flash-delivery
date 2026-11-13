"""Registro único de rutas HTTP por Lambda.

Lo consumen el stack CDK (rutas de API Gateway), los handlers (su router) y las pruebas
de contrato contra docs/api/openapi.json, de modo que no pueden desalinearse.
"""
ROUTES = {
    "identity": [
        "POST /api/v1/auth/dev-login",
        "GET /api/v1/auth/me",
    ],
    "stores": [
        "GET /api/v1/zones",
        "POST /api/v1/stores",
        "GET /api/v1/stores/me",
        "PATCH /api/v1/admin/stores/{storeId}",
    ],
    "couriers": [
        "POST /api/v1/couriers",
        "GET /api/v1/couriers/me",
        "PATCH /api/v1/couriers/me/availability",
        "GET /api/v1/couriers/me/active",
        "GET /api/v1/couriers/me/orders",
        "PATCH /api/v1/admin/couriers/{courierId}",
    ],
    "orders": [
        "POST /api/v1/orders",
        "GET /api/v1/orders/available",
        "GET /api/v1/orders/{orderId}",
        "GET /api/v1/orders/{orderId}/events",
        "GET /api/v1/stores/me/orders",
    ],
    "dispatch": [
        "POST /api/v1/orders/{orderId}/accept",
        "POST /api/v1/orders/{orderId}/pickup",
        "POST /api/v1/orders/{orderId}/deliver",
        "POST /api/v1/orders/{orderId}/cancel",
        "POST /api/v1/orders/{orderId}/fail",
    ],
    "availability": [
        "POST /api/v1/couriers/me/heartbeat",
        "DELETE /api/v1/couriers/me/heartbeat",
        "GET /api/v1/zones/{zoneId}/couriers",
    ],
    "tracking": [
        "GET /api/v1/tracking/{token}",
    ],
    "analytics": [
        "GET /api/v1/stores/me/stats",
    ],
}
