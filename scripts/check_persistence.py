"""Prueba explícita: reinicia MiniStack/Redis conservando datos y limpia solo sus UUID."""
import json
import subprocess
import time
from datetime import datetime, timezone
from uuid import uuid4
from backend.shared.config.settings import ROOT, Settings
from backend.shared.infrastructure.clients import DynamoDBAdapter, redis_client


def main():
    settings = Settings.load()
    ddb = DynamoDBAdapter(settings)
    cache = redis_client(settings)
    marker = uuid4().hex
    key = {"PK": {"S": "TEST#PERSISTENCE#" + marker}, "SK": {"S": "MARKER"}}
    redis_key = "flashdelivery:test:persistence:" + marker
    result = {"startedAt": datetime.now(timezone.utc).isoformat(), "marker": marker, "status": "failed"}
    report = ROOT / ".local/persistence.json"
    report.parent.mkdir(exist_ok=True)
    try:
        ddb.put_item(Item={**key, "marker": {"S": marker}})
        cache.set(redis_key, marker)
        subprocess.run(["docker", "compose", "restart", "ministack", "redis"], cwd=ROOT, check=True)
        subprocess.run(["docker", "compose", "up", "-d", "--wait", "ministack", "redis"], cwd=ROOT, check=True)
        # La disponibilidad de los servicios no implica que la tabla se haya restaurado aún.
        deadline = time.monotonic() + 30
        while True:
            try:
                item = ddb.get_item(Key=key, ConsistentRead=True).get("Item", {})
                assert item.get("marker") == {"S": marker}, "DynamoDB perdió el marcador"
                assert cache.get(redis_key) == marker, "Redis perdió el marcador"
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        result["status"] = "passed"
    finally:
        result["finishedAt"] = datetime.now(timezone.utc).isoformat()
        report.write_text(json.dumps(result, indent=2))
        try:
            ddb.client.delete_item(TableName=settings.table_name, Key=key)
        finally:
            cache.delete(redis_key)
            cache.close()
            ddb.client.close()
    print(f"Persistencia verificada tras reinicio. Evidencia: {report}")


if __name__ == "__main__":
    main()
