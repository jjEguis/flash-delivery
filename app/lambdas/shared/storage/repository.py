"""Lecturas por clave, cursores ligados a consulta y descriptores transaccionales."""
import base64
import binascii
from dataclasses import dataclass
import hashlib
import json

from lambdas.shared.storage import keys
from lambdas.shared.storage.model import deserialize, serialize, validate, validate_key


@dataclass(frozen=True)
class Page:
    items: list
    next_cursor: str | None = None


def page_limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("limit debe ser un entero entre 1 y 100")
    return value


def encode_cursor(scope, position):
    payload = {"v": 1, "scope": scope, "position": position}
    return base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode()


def decode_cursor(token, scope):
    try:
        if not isinstance(token, str) or len(token) > 8192:
            raise ValueError("cursor inválido")
        value = json.loads(base64.b64decode(token, altchars=b"-_", validate=True))
        if not isinstance(value, dict) or value.get("v") != 1 or value.get("scope") != scope:
            raise ValueError("cursor no corresponde a esta consulta")
        if not isinstance(value.get("position"), dict):
            raise ValueError("posición de cursor inválida")
        return value["position"]
    except (ValueError, TypeError, binascii.Error, UnicodeError) as exc:
        raise ValueError("Cursor inválido o de otra consulta") from exc


class Repository:
    entity_types = None

    def __init__(self, adapter):
        self.adapter = adapter

    def get(self, key):
        validate_key(key)
        response = self.adapter.get_item(Key=serialize(key), ConsistentRead=True)
        return deserialize(response["Item"]) if "Item" in response else None

    def query(self, partition, prefix, *, index=None, limit=25, cursor=None,
              descending=False, start=None, end=None):
        page_limit(limit)
        if index not in {None, "GSI1", "GSI2"}:
            raise ValueError("Índice inválido")
        pk, sk = (index + "PK", index + "SK") if index else ("PK", "SK")
        query = {"partition": partition, "prefix": prefix, "index": index,
                 "descending": descending, "start": keys.timestamp(start) if start else None,
                 "end": keys.timestamp(end) if end else None}
        if query["start"] and query["end"] and query["start"] > query["end"]:
            raise ValueError("Rango de fechas invertido")
        scope = hashlib.sha256(json.dumps(query, sort_keys=True).encode()).hexdigest()
        args = {"KeyConditionExpression": "#pk = :pk AND begins_with(#sk, :prefix)",
                "ExpressionAttributeNames": {"#pk": pk, "#sk": sk},
                "ExpressionAttributeValues": serialize({":pk": partition, ":prefix": prefix}),
                "Limit": limit, "ScanIndexForward": not descending, "ConsistentRead": index is None}
        if start or end:
            args["KeyConditionExpression"] = "#pk = :pk AND #sk BETWEEN :lo AND :hi"
            args["ExpressionAttributeValues"] = serialize({
                ":pk": partition,
                ":lo": prefix + query["start"] if start else prefix,
                ":hi": prefix + query["end"] + "#~" if end else prefix + "~",
            })
        if index:
            args["IndexName"] = index
        if cursor:
            position = decode_cursor(cursor, scope)
            expected = {"PK", "SK", pk, sk}
            if set(position) != expected:
                raise ValueError("Claves del cursor no corresponden a la consulta")
            validate_key(position)
            if index:
                validate_key(position, pk, sk)
            if position[pk] != partition or not position[sk].startswith(prefix):
                raise ValueError("Claves del cursor no corresponden a la consulta")
            args["ExclusiveStartKey"] = serialize(position)
        response = self.adapter.query(**args)
        last = response.get("LastEvaluatedKey")
        return Page([deserialize(item) for item in response["Items"]],
                    encode_cursor(scope, deserialize(last)) if last else None)

    def build_put(self, item, *, expected_version=None):
        validate(item)
        if self.entity_types is not None and item["entityType"] not in self.entity_types:
            raise ValueError("El módulo no es propietario de este tipo de ítem")
        if expected_version is not None and (type(expected_version) is not int or expected_version < 1):
            raise ValueError("expected_version inválida")
        action = {"TableName": self.adapter.settings.table_name, "Item": serialize(item),
                  "ConditionExpression": "attribute_not_exists(#pk)",
                  "ExpressionAttributeNames": {"#pk": "PK"}}
        if expected_version is not None:
            if item["version"] != expected_version + 1:
                raise ValueError("La versión nueva debe incrementar exactamente una unidad")
            action.update(ConditionExpression="attribute_exists(#pk) AND #version = :version",
                          ExpressionAttributeNames={"#pk": "PK", "#version": "version"},
                          ExpressionAttributeValues=serialize({":version": expected_version}))
        return {"Put": action}

    def build_delete(self, key, *, expected_version):
        validate_key(key)
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("expected_version inválida")
        return {"Delete": {"TableName": self.adapter.settings.table_name, "Key": serialize(key),
                           "ConditionExpression": "#version = :version",
                           "ExpressionAttributeNames": {"#version": "version"},
                           "ExpressionAttributeValues": serialize({":version": expected_version})}}

    def build_condition(self, key, expression, names, values):
        validate_key(key)
        return {"ConditionCheck": {"TableName": self.adapter.settings.table_name, "Key": serialize(key),
                                   "ConditionExpression": expression, "ExpressionAttributeNames": names,
                                   "ExpressionAttributeValues": serialize(values)}}
