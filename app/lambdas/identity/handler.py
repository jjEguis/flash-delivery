"""Identity: inicio de sesión de desarrollo y consulta del actor actual."""
import hmac
import os

from lambdas.identity.contracts import ActorContext
from lambdas.identity.tokens import issue
from lambdas.shared.exceptions import ForbiddenError, ValidationError
from lambdas.shared.http import router

LOCAL_ADMIN_CODE = "admin-local"


def dev_login(request):
    """POST /api/v1/auth/dev-login — solo entorno local (Settings rechaza otros entornos).

    STORE y COURIER entran con cualquier userId válido; ADMIN exige el código configurado
    en DEV_ADMIN_CODE. Nunca debe exponerse fuera de desarrollo.
    """
    data = request.json()
    role = data.get("role")
    if role not in {"STORE", "COURIER", "ADMIN"}:
        raise ValidationError("role debe ser STORE, COURIER o ADMIN")
    if role == "ADMIN":
        code = os.getenv("DEV_ADMIN_CODE", LOCAL_ADMIN_CODE)
        if not isinstance(data.get("adminCode"), str) or not hmac.compare_digest(data["adminCode"], code):
            raise ForbiddenError("Código de administrador incorrecto", "INVALID_ADMIN_CODE")
    actor = ActorContext(data.get("userId") if isinstance(data.get("userId"), str) else "", role)
    token, expires = issue(actor)
    return 200, {"token": token, "expiresAt": expires, "actor": {"actorId": actor.actor_id, "role": actor.role}}


def me(request):
    """GET /api/v1/auth/me"""
    actor = request.actor
    return 200, {"actorId": actor.actor_id, "role": actor.role}


ROUTES = {
    "POST /api/v1/auth/dev-login": dev_login,
    "GET /api/v1/auth/me": me,
}
main = router(ROUTES)
