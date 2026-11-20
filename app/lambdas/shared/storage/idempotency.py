"""Persistencia técnica del resultado; la política de reintentos pertenece a SPEC-02."""
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import Repository


def idempotency_record(scope, request_id, payload_hash, result, created_at):
    return make_item("IDEMPOTENCY", scope=scope, requestId=request_id,
                     payloadHash=payload_hash, result=result, createdAt=created_at)


class IdempotencyRepository(Repository):
    entity_types = {"IDEMPOTENCY"}

    def get_result(self, scope, request_id):
        return self.get(keys.request(scope, request_id))
