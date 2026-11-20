"""Pruebas del adaptador técnico con moto; sin implementar pedidos anticipadamente."""
import pytest
from botocore.exceptions import ClientError
from lambdas.shared.infrastructure.clients import DynamoDBAdapter


def test_put_get_update_y_query_gsi(tabla_dynamodb):
    adapter = DynamoDBAdapter(client=tabla_dynamodb)
    key = {"PK": {"S": "TEST#1"}, "SK": {"S": "META"}}
    adapter.put_item(Item={**key, "GSI1PK": {"S": "STORE#1"}, "GSI1SK": {"S": "ORDER#1"}})
    adapter.update_item(Key=key, UpdateExpression="SET #v = :v",
                        ExpressionAttributeNames={"#v": "version"},
                        ExpressionAttributeValues={":v": {"N": "1"}})
    assert adapter.get_item(Key=key, ConsistentRead=True)["Item"]["version"] == {"N": "1"}
    result = adapter.query(IndexName="GSI1", KeyConditionExpression="GSI1PK = :pk",
                           ExpressionAttributeValues={":pk": {"S": "STORE#1"}})
    assert [item["PK"] for item in result["Items"]] == [{"S": "TEST#1"}]


def test_transaccion_rollback_sin_escrituras_parciales(tabla_dynamodb):
    adapter = DynamoDBAdapter(client=tabla_dynamodb)
    key = {"PK": {"S": "TEST#1"}, "SK": {"S": "META"}}
    second = {"PK": {"S": "TEST#2"}, "SK": {"S": "META"}}
    adapter.transact_write_items([{"Put": {"TableName": "test-tabla", "Item": key}}])
    with pytest.raises(ClientError) as error:
        adapter.transact_write_items([
            {"Put": {"TableName": "test-tabla", "Item": second}},
            {"Put": {"TableName": "test-tabla", "Item": key,
                     "ConditionExpression": "attribute_not_exists(PK)"}},
        ])
    assert error.value.response["Error"]["Code"] == "TransactionCanceledException"
    assert "Item" not in adapter.get_item(Key=second, ConsistentRead=True)


def test_transaccion_rechaza_otra_tabla(tabla_dynamodb):
    adapter = DynamoDBAdapter(client=tabla_dynamodb)
    with pytest.raises(ValueError, match="tabla configurada"):
        adapter.transact_write_items([{"Put": {"TableName": "otra-tabla", "Item": {}}}])
