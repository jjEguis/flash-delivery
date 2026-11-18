"""GSI2 para bandejas; auditoría propia por clave, sin Scan."""
from lambdas.shared.storage.repository import Repository
from lambdas.shared.storage import keys


def audit_partition(kind, identity):
    return f'PROFILE_AUDIT#{kind}#{keys.identifier(identity)}'


class ApprovalsRepository(Repository):
    entity_types = {'PROFILE_AUDIT'}

    def list_profiles(self, kind, status, **page):
        return self.query(f'ADMIN#{kind}#{status}', 'CREATED#', index='GSI2', descending=True, **page)

    def events(self, kind, identity, **page):
        return self.query(audit_partition(kind, identity), 'EVENT#', descending=True, **page)
