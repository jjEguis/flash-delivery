"""Ejecución de comandos: un único commit DynamoDB que incluye el resultado idempotente.

Cada comando entrega una función `build()` que lee el estado actual (lecturas fuertes),
devuelve pares (acción transaccional, error de dominio si su condición falla) y el
resultado a persistir. Un reintento con la misma clave y la misma huella devuelve el
resultado guardado sin volver a mutar; con otra huella produce IDEMPOTENCY_CONFLICT.
"""
import hashlib
import json
import logging
import random
import time

from botocore.exceptions import BotoCoreError, ClientError

from lambdas.shared.exceptions import ConflictError, DependencyUnavailableError, ValidationError
from lambdas.shared.storage import keys
from lambdas.shared.storage.idempotency import IdempotencyRepository, idempotency_record

logger = logging.getLogger(__name__)
CONFLICT_RETRIES = 3


def payload_hash(payload):
    """Huella canónica de los campos de negocio (sin hora ni requestId de trazabilidad)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _replay(repo, scope, request_id, digest):
    try:
        record = repo.get_result(scope, request_id)
    except (ClientError, BotoCoreError) as exc:
        raise DependencyUnavailableError("No se pudo consultar el resultado previo") from exc
    if record is None:
        return None
    if record["payloadHash"] != digest:
        raise ConflictError("La clave de idempotencia ya se usó con otro contenido", "IDEMPOTENCY_CONFLICT")
    return record["result"]


def run_command(adapter, *, actor_id, operation, request_id, payload, build, now):
    """Ejecuta `build` y confirma sus acciones junto con el registro idempotente."""
    try:
        keys.identifier(request_id)
    except ValueError as exc:
        raise ValidationError("Idempotency-Key obligatoria: 1–128 letras, números, guion o guion bajo") from exc
    scope = keys.request_scope(actor_id, operation)
    repo = IdempotencyRepository(adapter)
    digest = payload_hash(payload)
    previous = _replay(repo, scope, request_id, digest)
    if previous is not None:
        return previous
    for attempt in range(CONFLICT_RETRIES):
        pairs, result = build()
        actions = [action for action, _ in pairs]
        errors = [error for _, error in pairs]
        actions.append(repo.build_put(idempotency_record(scope, request_id, digest, result, now)))
        try:
            adapter.transact_write_items(actions)
            return result
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "TransactionCanceledException":
                raise DependencyUnavailableError("DynamoDB no está disponible") from exc
            # Otra solicitud con la misma clave pudo confirmar primero.
            previous = _replay(repo, scope, request_id, digest)
            if previous is not None:
                return previous
            reasons = [reason.get("Code") for reason in exc.response.get("CancellationReasons") or []]
            for index, code in enumerate(reasons):
                if code == "ConditionalCheckFailed" and index < len(errors) and errors[index] is not None:
                    raise errors[index] from None
            if "TransactionConflict" in reasons and attempt + 1 < CONFLICT_RETRIES:
                # Carrera con otra transacción sobre los mismos ítems: releer y reintentar.
                time.sleep(random.uniform(0.01, 0.05) * (attempt + 1))
                continue
            logger.warning("Transacción cancelada %s: %s", operation, reasons)
            raise ConflictError("El recurso cambió mientras se procesaba; vuelve a intentarlo",
                                "CONCURRENT_UPDATE") from None
        except BotoCoreError as exc:
            raise DependencyUnavailableError("DynamoDB no está disponible") from exc
    raise ConflictError("El recurso cambió mientras se procesaba; vuelve a intentarlo", "CONCURRENT_UPDATE")
