"""Sonda de dependencias ejecutada desde un paquete Lambda real."""
import json
import logging
from backend.shared.config.settings import Settings
from backend.shared.infrastructure.clients import aws_client, redis_client

logger = logging.getLogger(__name__)


def handler(event, context):
    settings = Settings.load()
    checks = {}
    ddb = aws_client("dynamodb", settings)
    cache = redis_client(settings)
    try:
        try:
            ddb.describe_table(TableName=settings.table_name)
            checks["dynamodb"] = "ok"
        except Exception:
            logger.exception("Readiness DynamoDB falló")
            checks["dynamodb"] = "unavailable"
        try:
            checks["redis"] = "ok" if cache.ping() else "unavailable"
        except Exception:
            logger.exception("Readiness Redis falló")
            checks["redis"] = "unavailable"
    finally:
        ddb.close()
        cache.close()
    ready = all(value == "ok" for value in checks.values())
    return {"statusCode": 200 if ready else 503,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"service": "flashdelivery", "status": "ok" if ready else "unavailable",
                                "environment": "local", "checks": checks})}
