from lambdas.shared.storage import keys
from lambdas.shared.storage.model import make_item, serialize
from lambdas.shared.storage.repository import Repository


def store_stats(store_id, month, delivered_count, total_fee_minor, updated_at, version=1):
    return make_item("STORE_STATS", storeId=store_id, month=month, deliveredCount=delivered_count,
                     totalFeeMinor=total_fee_minor, updatedAt=updated_at, version=version)


class AnalyticsRepository(Repository):
    entity_types = {"STORE_STATS"}

    def get_month(self, store_id, month):
        return self.get(keys.stats(store_id, month))

    def build_increment(self, store_id, month, fee_minor, updated_at):
        """Contador atómico (ADD) para sumar una entrega dentro de la transacción de entrega.

        No requiere leer el agregado: entregas simultáneas del mismo comercio no compiten
        por una versión. Crea el ítem con su esquema completo la primera vez (if_not_exists).
        Que cada entrega cuente una sola vez lo garantiza la condición de estado del pedido
        en la misma transacción, no este Update.
        """
        if type(fee_minor) is not int or fee_minor < 0:
            raise ValueError("fee_minor debe ser entero no negativo")
        key = keys.stats(store_id, month)
        names = {"#type": "entityType", "#schema": "schemaVersion", "#store": "storeId",
                 "#month": "month", "#updated": "updatedAt", "#count": "deliveredCount",
                 "#fee": "totalFeeMinor", "#version": "version"}
        values = {":type": "STORE_STATS", ":schema": 1, ":store": keys.identifier(store_id),
                  ":month": keys.month(month), ":updated": keys.timestamp(updated_at),
                  ":one": 1, ":fee": fee_minor}
        return {"Update": {
            "TableName": self.adapter.settings.table_name, "Key": serialize(key),
            "UpdateExpression": ("SET #type = if_not_exists(#type, :type), #schema = if_not_exists(#schema, :schema), "
                                 "#store = if_not_exists(#store, :store), #month = if_not_exists(#month, :month), "
                                 "#updated = :updated ADD #count :one, #fee :fee, #version :one"),
            "ExpressionAttributeNames": names, "ExpressionAttributeValues": serialize(values)}}
