"""Aprobaciones: perfil y auditoría atómicos, estado fuerte y guard ACTIVE."""
from lambdas.identity.contracts import authorize
from lambdas.shared import clock
from lambdas.shared.exceptions import ConflictError, NotFoundError, ValidationError
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import APPROVAL_STATES, make_item, profile_status
from lambdas.shared.storage.repository import Page, page_dto
from lambdas.shared.storage.transactions import commit
from lambdas.stores.repository import StoresRepository
from lambdas.couriers.repository import CouriersRepository
from lambdas.approvals.repository import ApprovalsRepository

REPOSITORIES = {'STORE': StoresRepository, 'COURIER': CouriersRepository}
PHYSICAL = {'PK','SK','GSI1PK','GSI1SK','GSI2PK','GSI2SK','entityType','schemaVersion'}


def load(adapter, kind, identity):
    try:
        value = REPOSITORIES[kind](adapter).get_profile(identity)
    except ValueError as exc:
        raise ValidationError('Identificador de perfil inválido') from exc
    if value is None:
        raise NotFoundError('Perfil no encontrado', f'{kind}_NOT_FOUND')
    return value


def view(profile):
    fields = ('storeId','courierId','name','zoneId','enabled','available','createdAt','updatedAt','version')
    return {**{k:profile[k] for k in fields if k in profile}, 'approvalStatus':profile_status(profile)}


def detail(adapter, actor, kind, identity):
    authorize(actor, 'ADMIN')
    profile = load(adapter, kind, identity)
    result = view(profile)
    if kind == 'COURIER':
        active = CouriersRepository(adapter).get_active(identity)
        result['activeOrderId'] = active['orderId'] if active else None
    return result


def listing(adapter, actor, kind, status, page):
    authorize(actor, 'ADMIN')
    if not isinstance(status, str) or status not in APPROVAL_STATES:
        raise ValidationError('status debe ser PENDING, ENABLED o SUSPENDED')
    def query():
        result = ApprovalsRepository(adapter).list_profiles(kind, status, **page)
        current = []
        # El GSI es eventual: no autoriza ni determina el estado de una acción.
        repo = REPOSITORIES[kind](adapter)
        for item in result.items:
            identity = item['storeId' if kind == 'STORE' else 'courierId']
            profile = repo.get_profile(identity)
            if profile and profile_status(profile) == status:
                current.append(profile)
        return Page(current, result.next_cursor)
    return page_dto(query, view)


def events(adapter, actor, kind, identity, page):
    authorize(actor, 'ADMIN')
    load(adapter, kind, identity)
    return page_dto(lambda: ApprovalsRepository(adapter).events(kind, identity, **page),
                    lambda item: {k:v for k,v in item.items() if k not in PHYSICAL})


def change(adapter, actor, kind, identity, enabled, *, expected_version=None, reason=None):
    authorize(actor, 'ADMIN')
    if type(enabled) is not bool:
        raise ValidationError('enabled debe ser booleano')
    if expected_version is not None and (type(expected_version) is not int or expected_version < 1):
        raise ValidationError('expectedVersion debe ser entero positivo')
    if reason is not None and (not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 300):
        raise ValidationError('reason debe tener 1–300 caracteres')
    old = load(adapter, kind, identity)
    target = 'ENABLED' if enabled else 'SUSPENDED'
    previous = profile_status(old)
    if previous == target:
        return old  # reintento/no-op no produce auditoría ni incrementa versión
    if expected_version is not None and old['version'] != expected_version:
        raise ConflictError('El perfil cambió; actualiza antes de confirmar', 'PROFILE_CHANGED')
    repo = REPOSITORIES[kind](adapter)
    data = {k:v for k,v in old.items() if k not in PHYSICAL}
    now = max(clock.now(), old['updatedAt'])
    data.update(enabled=enabled, approvalStatus=target, version=old['version']+1, updatedAt=now)
    if kind == 'COURIER' and not enabled:
        data['available'] = False
    new = make_item(kind, **data)
    audit = make_item('PROFILE_AUDIT', profileKind=kind, profileId=identity, actorId=actor.actor_id,
                      occurredAt=now, eventId=clock.new_id('a_'), fromStatus=previous, toStatus=target,
                      profileVersion=new['version'], reason=reason.strip() if reason is not None else 'Sin motivo informado (cliente anterior)')
    pairs = [(repo.build_put(new, expected_version=old['version']),
              ConflictError('El perfil cambió; actualiza antes de confirmar', 'PROFILE_CHANGED')),
             (ApprovalsRepository(adapter).build_put(audit), None)]
    if kind == 'COURIER' and not enabled:
        # Misma transacción que escribe el perfil: compite correctamente con accept_order.
        guard = repo.build_condition(keys.active(identity), 'attribute_not_exists(#pk)', {'#pk':'PK'}, {})
        guard['ConditionCheck'].pop('ExpressionAttributeValues')
        pairs.append((guard,
                      ConflictError('Tiene una entrega activa. Finalízala o resuélvela antes de suspender.', 'COURIER_HAS_ACTIVE_ORDER')))
    commit(adapter, pairs)
    return new
