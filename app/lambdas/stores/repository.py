"""Perfiles de comercio y participación explícita en una transacción."""
from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import Repository


def store_profile(*, store_id, owner_id, zone_id, name, enabled, created_at, updated_at=None, version=1):
    return make_item("STORE", storeId=store_id, ownerId=owner_id, zoneId=zone_id,
                     name=name, enabled=enabled, createdAt=created_at,
                     updatedAt=updated_at or created_at, version=version)


class StoresRepository(Repository):
    entity_types = {"STORE"}

    def get_profile(self, store_id):
        return self.get(keys.profile(keys.store(store_id)))

    def build_enabled_condition(self, store_id, version):
        return self.build_condition(keys.profile(keys.store(store_id)), "#enabled = :yes AND #v = :v",
                                    {"#enabled": "enabled", "#v": "version"}, {":yes": True, ":v": version})
