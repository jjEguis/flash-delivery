"""Stores: catálogo de zonas, alta del comercio propio y habilitación administrativa (CU01)."""
import os

from lambdas.identity.contracts import ActorContext, authorize
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, NotFoundError, ValidationError
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.transactions import commit
from lambdas.stores.repository import StoresRepository, store_profile

DEFAULT_ZONES = "centro:Centro,norte:Norte,sur:Sur,oriente:Oriente,occidente:Occidente"
PHYSICAL = {"PK", "SK", "entityType", "schemaVersion"}


def zones():
    """Zonas predefinidas (ADR-006), configurables con ZONES=id:Nombre,..."""
    result = []
    for entry in os.getenv("ZONES", DEFAULT_ZONES).split(","):
        zone_id, _, name = entry.strip().partition(":")
        result.append({"zoneId": keys.identifier(zone_id), "name": name or zone_id})
    return result


def require_zone(zone_id):
    if zone_id not in {zone["zoneId"] for zone in zones()}:
        raise ValidationError("zoneId no pertenece al catálogo de zonas", "INVALID_ZONE")
    return zone_id


def profile_name(value):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
        raise ValidationError("name debe ser texto de 1 a 120 caracteres")
    return value.strip()


def store_view(store):
    return {name: store[name] for name in ("storeId", "name", "zoneId", "enabled", "createdAt",
                                           "updatedAt", "version")}


def register_store(adapter, actor: ActorContext, *, name, zone_id):
    """Crea el perfil del comercio del actor, deshabilitado hasta que un ADMIN lo apruebe."""
    authorize(actor, "STORE")
    repo = StoresRepository(adapter)
    store = store_profile(store_id=actor.store_id, owner_id=actor.actor_id, zone_id=require_zone(zone_id),
                          name=profile_name(name), enabled=False, created_at=clock.now())
    commit(adapter, [(repo.build_put(store), ConflictError("Ya registraste tu comercio", "STORE_ALREADY_REGISTERED"))])
    return store_view(store)


def get_my_store(adapter, actor: ActorContext):
    authorize(actor, "STORE")
    store = StoresRepository(adapter).get_profile(actor.store_id)
    if store is None:
        raise NotFoundError("Aún no registras tu comercio", "STORE_NOT_REGISTERED")
    return store_view(store)


def set_store_enabled(adapter, actor: ActorContext, store_id, enabled):
    """Habilitación administrativa con bloqueo optimista por versión."""
    authorize(actor, "ADMIN")
    if type(enabled) is not bool:
        raise ValidationError("enabled debe ser booleano")
    repo = StoresRepository(adapter)
    try:
        store = repo.get_profile(store_id)
    except ValueError as exc:
        raise ValidationError("storeId inválido") from exc
    if store is None:
        raise NotFoundError("Comercio no encontrado", "STORE_NOT_FOUND")
    if store["enabled"] == enabled:
        return store_view(store)
    data = {k: v for k, v in store.items() if k not in PHYSICAL}
    data.update(enabled=enabled, updatedAt=max(clock.now(), store["updatedAt"]), version=store["version"] + 1)
    new = make_item("STORE", **data)
    commit(adapter, [(repo.build_put(new, expected_version=store["version"]),
                      ConflictError("El comercio cambió; vuelve a intentarlo", "STORE_CHANGED"))])
    return store_view(new)
