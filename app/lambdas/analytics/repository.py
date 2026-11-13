from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item
from lambdas.shared.storage.repository import Repository


def store_stats(store_id, month, delivered_count, total_fee_minor, updated_at, version=1):
    return make_item("STORE_STATS", storeId=store_id, month=month, deliveredCount=delivered_count,
                     totalFeeMinor=total_fee_minor, updatedAt=updated_at, version=version)


class AnalyticsRepository(Repository):
    entity_types = {"STORE_STATS"}

    def get_month(self, store_id, month):
        return self.get(keys.stats(store_id, month))
