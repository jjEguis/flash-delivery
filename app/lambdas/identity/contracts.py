"""Contexto del actor autenticado que reciben los servicios de aplicación."""
from dataclasses import dataclass

from lambdas.shared.exceptions import ForbiddenError, ValidationError
from lambdas.shared.storage import keys

ROLES = {"ADMIN", "STORE", "COURIER"}


@dataclass(frozen=True)
class ActorContext:
    """Identidad verificada. En el MVP cada usuario STORE/COURIER tiene un solo perfil
    y su ID coincide con el del actor, de modo que la pertenencia la fija el servidor."""
    actor_id: str
    role: str

    def __post_init__(self):
        try:
            keys.identifier(self.actor_id)
        except ValueError as exc:
            raise ValidationError("Identificador de actor inválido") from exc
        if self.role not in ROLES:
            raise ValidationError("Rol inválido")

    @property
    def store_id(self):
        return self.actor_id if self.role == "STORE" else None

    @property
    def courier_id(self):
        return self.actor_id if self.role == "COURIER" else None


def authorize(actor, *roles):
    """Exige uno de los roles indicados."""
    if not isinstance(actor, ActorContext) or actor.role not in roles:
        raise ForbiddenError("Esta operación no está permitida para tu rol")
    return actor
