"""Fábricas locales: sin conexiones durante la importación."""
import boto3
from botocore.config import Config
from redis import Redis
from backend.shared.config.settings import Settings


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


class DynamoDBAdapter:
    """API de infraestructura con formato AttributeValue de DynamoDB.

    Los futuros repositorios de cada módulo traducirán entidades a este formato.
    Query devuelve LastEvaluatedKey; el consumidor debe paginar explícitamente.
    """
    def __init__(self, settings=None):
        self.settings = settings or Settings.load()
        self.client = aws_client("dynamodb", self.settings)

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
        for item in items:
            if len(item) != 1:
                raise ValueError("Cada operación debe tener una única acción")
            action = next(iter(item.values()))
            if action.get("TableName") != self.settings.table_name:
                raise ValueError("La transacción solo puede usar la tabla configurada")
        return self.client.transact_write_items(TransactItems=items, **kwargs)
