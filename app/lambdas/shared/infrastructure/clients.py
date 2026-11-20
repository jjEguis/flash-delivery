"""Fábricas locales: sin conexiones durante la importación."""
import boto3
import json
from botocore.config import Config
from redis import Redis
from lambdas.shared.config.settings import Settings


def aws_client(service, settings=None):
    settings = settings or Settings.load()
    return boto3.session.Session(
        aws_access_key_id="test", aws_secret_access_key="test",
        aws_session_token="", region_name=settings.region,
    ).client(service, endpoint_url=settings.endpoint, config=Config(
        connect_timeout=settings.connect_timeout, read_timeout=settings.read_timeout,
        retries={"max_attempts": 2, "mode": "standard"}, proxies={},
    ))


def redis_client(settings=None):
    settings = settings or Settings.load()
    return Redis(host=settings.redis_host, port=settings.redis_port,
                 socket_connect_timeout=settings.connect_timeout,
                 socket_timeout=settings.read_timeout, decode_responses=True)


_SHARED = {}


def shared_adapter():
    """Adaptador reutilizado entre invocaciones de una misma Lambda caliente (lazy)."""
    if "adapter" not in _SHARED:
        _SHARED["adapter"] = DynamoDBAdapter()
    return _SHARED["adapter"]


def shared_redis():
    """Cliente Redis reutilizado entre invocaciones; redis-py reconecta si se cae."""
    if "redis" not in _SHARED:
        _SHARED["redis"] = redis_client()
    return _SHARED["redis"]


class DynamoDBAdapter:
    """API de infraestructura con formato AttributeValue de DynamoDB.

    Los futuros repositorios de cada módulo traducirán entidades a este formato.
    Query devuelve LastEvaluatedKey; el consumidor debe paginar explícitamente.
    """
    def __init__(self, settings=None, client=None):
        self.settings = settings or Settings.load()
        self.client = client if client is not None else aws_client("dynamodb", self.settings)

    def get_item(self, **kwargs):
        return self.client.get_item(TableName=self.settings.table_name, **kwargs)

    def put_item(self, **kwargs):
        return self.client.put_item(TableName=self.settings.table_name, **kwargs)

    def update_item(self, **kwargs):
        return self.client.update_item(TableName=self.settings.table_name, **kwargs)

    def query(self, **kwargs):
        return self.client.query(TableName=self.settings.table_name, **kwargs)

    def transact_write_items(self, items, **kwargs):
        # Evita que una transacción alcance otras tablas.
        if not 1 <= len(items) <= 100:
            raise ValueError("Transacción requiere entre 1 y 100 acciones")
        seen = set()
        for item in items:
            if len(item) != 1:
                raise ValueError("Cada operación debe tener una única acción")
            if next(iter(item)) not in {"Put", "Update", "Delete", "ConditionCheck"}:
                raise ValueError("Acción transaccional inválida")
            action = next(iter(item.values()))
            if action.get("TableName") != self.settings.table_name:
                raise ValueError("La transacción solo puede usar la tabla configurada")
            key = action.get("Key", action.get("Item", {}))
            try:
                identity = (key["PK"]["S"], key["SK"]["S"])
            except (KeyError, TypeError) as exc:
                raise ValueError("Acción requiere PK/SK String") from exc
            from lambdas.shared.storage.model import validate_key
            validate_key({"PK": identity[0], "SK": identity[1]})
            if identity in seen:
                raise ValueError("No se permiten dos acciones sobre el mismo ítem")
            seen.add(identity)
        if len(json.dumps(items, ensure_ascii=False).encode("utf-8")) > 4 * 1024 * 1024:
            raise ValueError("Transacción excede límite conservador de 4 MiB")
        return self.client.transact_write_items(TransactItems=items, **kwargs)
