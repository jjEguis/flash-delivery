"""Esquema físico v1: validación y serialización de JSON a AttributeValue."""
import json
import re
from decimal import Decimal
from boto3.dynamodb.types import TypeSerializer, TypeDeserializer
from lambdas.shared.storage import keys

REQUIRED = {
    "STORE": {"storeId", "ownerId", "zoneId", "name", "enabled", "createdAt", "updatedAt"},
    "COURIER": {"courierId", "ownerId", "zoneId", "name", "enabled", "available", "createdAt", "updatedAt"},
    "ORDER": {"orderId", "storeId", "zoneId", "status", "createdAt", "updatedAt", "pickupAddress",
              "dropoffAddress", "feeMinor", "currency", "trackingTokenHash"},
    "ORDER_EVENT": {"orderId", "eventId", "eventType", "occurredAt"},
    "ACTIVE_ASSIGNMENT": {"courierId", "orderId", "assignedAt"},
    "COURIER_ORDER_VIEW": {"courierId", "orderId", "storeId", "status", "createdAt", "updatedAt"},
    "STORE_STATUS_VIEW": {"storeId", "orderId", "status", "createdAt", "updatedAt"},
    "STORE_STATS": {"storeId", "month", "deliveredCount", "totalFeeMinor", "updatedAt"},
    "IDEMPOTENCY": {"scope", "requestId", "payloadHash", "result", "createdAt"},
}
SERIALIZER, DESERIALIZER = TypeSerializer(), TypeDeserializer()


def validate_json(value, depth=0):
    if depth > 32:
        raise ValueError("Datos exceden 32 niveles de anidamiento")
    if value is None or type(value) in (str, bool):
        return
    if type(value) is int:
        if len(str(abs(value))) > 38:
            raise ValueError("Número excede 38 dígitos")
        return
    if isinstance(value, dict):
        for name, child in value.items():
            if not isinstance(name, str) or not name:
                raise ValueError("Nombre de atributo debe ser String no vacío")
            validate_json(child, depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            validate_json(child, depth + 1)
        return
    raise ValueError("Solo se admiten valores JSON sin float ni binarios")


def serialize(item):
    return {name: SERIALIZER.serialize(value) for name, value in item.items()}


def deserialize(item):
    def native(value):
        if isinstance(value, Decimal):
            return int(value) if value == value.to_integral_value() else value
        if isinstance(value, dict):
            return {k: native(v) for k, v in value.items()}
        if isinstance(value, list):
            return [native(v) for v in value]
        return value
    return native({name: DESERIALIZER.deserialize(value) for name, value in item.items()})


def validate_key(item, pk="PK", sk="SK"):
    for name, maximum in ((pk, 2048), (sk, 1024)):
        value = item.get(name)
        if not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= maximum:
            raise ValueError(f"{name} debe ser String de 1 a {maximum} bytes")


def layout(kind, data):
    """Claves calculadas: el llamador nunca puede inyectar índices arbitrarios."""
    if kind == "STORE":
        return keys.profile(keys.store(data["storeId"]))
    if kind == "COURIER":
        return keys.profile(keys.courier(data["courierId"]))
    if kind == "ACTIVE_ASSIGNMENT":
        return keys.active(data["courierId"])
    if kind == "ORDER_EVENT":
        return keys.event(data["orderId"], data["occurredAt"], data["eventId"])
    if kind == "STORE_STATS":
        return keys.stats(data["storeId"], data["month"])
    if kind == "IDEMPOTENCY":
        return keys.request(data["scope"], data["requestId"])
    if kind == "STORE_STATUS_VIEW":
        return {**keys.store_view(data["storeId"], data["orderId"]),
                "GSI2PK": keys.store_state(data["storeId"], data["status"]),
                "GSI2SK": keys.created(data["createdAt"], data["orderId"])}
    if kind == "COURIER_ORDER_VIEW":
        return {**keys.courier_view(data["courierId"], data["orderId"]),
                "GSI1PK": keys.courier(data["courierId"]),
                "GSI1SK": keys.history(data["createdAt"], data["orderId"])}
    result = {**keys.meta(data["orderId"]), "GSI1PK": keys.store(data["storeId"]),
              "GSI1SK": keys.history(data["createdAt"], data["orderId"])}
    if data["status"] == "PENDING":
        result.update(GSI2PK=keys.zone_open(data["zoneId"]),
                      GSI2SK=keys.created(data["createdAt"], data["orderId"]))
    return result


def validate(item):
    if not isinstance(item, dict):
        raise ValueError("Ítem debe ser objeto")
    validate_json(item)
    kind = item.get("entityType")
    if not isinstance(kind, str) or kind not in REQUIRED or not REQUIRED[kind] <= item.keys():
        raise ValueError("Tipo o atributos obligatorios inválidos")
    if type(item.get("schemaVersion")) is not int or item["schemaVersion"] != 1:
        raise ValueError("schemaVersion debe ser 1")
    if type(item.get("version")) is not int or item["version"] < 1:
        raise ValueError("version debe ser entero positivo")
    optional = {"courierId"} if kind == "ORDER" else set()
    allowed = REQUIRED[kind] | optional | {"entityType", "schemaVersion", "version", "PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"}
    if item.keys() - allowed:
        raise ValueError("Atributos fuera del esquema")
    for name in ("storeId", "courierId", "orderId", "ownerId", "zoneId", "eventId", "requestId"):
        if name in item:
            keys.identifier(item[name])
    for name in ("createdAt", "updatedAt", "assignedAt", "occurredAt"):
        if name in item and keys.timestamp(item[name]) != item[name]:
            raise ValueError(f"{name} debe estar en UTC con seis decimales y sufijo Z")
    if "status" in item:
        keys.status(item["status"])
    for name in ("enabled", "available"):
        if name in item and type(item[name]) is not bool:
            raise ValueError(f"{name} debe ser booleano")
    for name in ("feeMinor", "deliveredCount", "totalFeeMinor"):
        if name in item and (type(item[name]) is not int or item[name] < 0):
            raise ValueError(f"{name} debe ser entero no negativo")
    for name in ("name", "pickupAddress", "dropoffAddress"):
        if name in item and (not isinstance(item[name], str) or not item[name].strip()):
            raise ValueError(f"{name} debe ser texto no vacío")
    for name in ("trackingTokenHash", "payloadHash"):
        if name in item and (not isinstance(item[name], str) or not re.fullmatch(r"[0-9a-f]{64}", item[name])):
            raise ValueError(f"{name} debe ser SHA-256 hexadecimal")
    if "currency" in item and (not isinstance(item["currency"], str) or not re.fullmatch(r"[A-Z]{3}", item["currency"])):
        raise ValueError("currency debe tener tres letras mayúsculas")
    if kind == "ORDER":
        if item["status"] in {"ASSIGNED", "PICKED_UP", "DELIVERED", "FAILED"} and "courierId" not in item:
            raise ValueError("Estado requiere courierId")
        if item["status"] == "PENDING" and "courierId" in item:
            raise ValueError("Pedido PENDING no puede tener courierId")
    if kind == "ORDER_EVENT" and (not isinstance(item["eventType"], str) or item["eventType"] not in {"CREATED", "ASSIGNED", "PICKED_UP", "DELIVERED", "CANCELLED", "FAILED"}):
        raise ValueError("eventType inválido")
    if kind == "IDEMPOTENCY" and not isinstance(item["result"], dict):
        raise ValueError("result debe ser un objeto")
    if "createdAt" in item and "updatedAt" in item and item["updatedAt"] < item["createdAt"]:
        raise ValueError("updatedAt no puede preceder createdAt")
    expected = layout(kind, item)
    for name in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK"):
        if item.get(name) != expected.get(name) or (name in item and name not in expected):
            raise ValueError(f"Clave {name} no coincide con el esquema")
    validate_key(item)
    for index in ("GSI1", "GSI2"):
        if index + "PK" in item:
            validate_key(item, index + "PK", index + "SK")
    # El JSON AttributeValue sobreestima el tamaño real: límite conservador.
    try:
        size = len(json.dumps(serialize(item), ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Solo se admiten valores JSON sin float ni binarios") from exc
    if size > 400 * 1024:
        raise ValueError("Ítem excede límite conservador de 400 KiB")
    return item


def make_item(kind, **data):
    if not isinstance(kind, str) or kind not in REQUIRED:
        raise ValueError("entityType inválido")
    data = {**data, "entityType": kind, "schemaVersion": 1}
    data.setdefault("version", 1)
    for name in ("createdAt", "updatedAt", "assignedAt", "occurredAt"):
        if name in data:
            data[name] = keys.timestamp(data[name])
    if not REQUIRED[kind] <= data.keys():
        raise ValueError("Faltan atributos obligatorios")
    return validate({**data, **layout(kind, data)})
