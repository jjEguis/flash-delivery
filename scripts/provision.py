"""Aplica la plantilla CDK únicamente al endpoint local validado."""
import json
from botocore.exceptions import ClientError, WaiterError
from backend.shared.config.settings import ROOT, Settings
from backend.shared.infrastructure.clients import aws_client
from infrastructure.cdk.app import synthesize
from scripts.package_lambda import publish_package

STACK = "FlashDeliveryLocal"


def main():
    settings = Settings.load()
    package_key = publish_package(settings)
    template = json.dumps(synthesize(package_key))
    client = aws_client("cloudformation", settings)
    parameters = dict(StackName=STACK, TemplateBody=template, Capabilities=["CAPABILITY_IAM"])
    try:
        client.describe_stacks(StackName=STACK)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ValidationError" or "does not exist" not in str(exc):
            raise
        client.create_stack(**parameters)
        waiter = "stack_create_complete"
    else:
        try:
            client.update_stack(**parameters)
            waiter = "stack_update_complete"
        except ClientError as exc:
            if "No updates are to be performed" not in str(exc):
                raise
            waiter = None
    if waiter:
        try:
            client.get_waiter(waiter).wait(StackName=STACK, WaiterConfig={"Delay": 2, "MaxAttempts": 90})
        except WaiterError:
            print(json.dumps(client.describe_stack_events(StackName=STACK)["StackEvents"], default=str, indent=2))
            raise
    outputs = {entry["OutputKey"]: entry["OutputValue"] for entry in
               client.describe_stacks(StackName=STACK)["Stacks"][0].get("Outputs", [])}
    url = f"{settings.endpoint}/_aws/execute-api/{outputs['ApiId']}/local/health"
    (ROOT / ".local").mkdir(exist_ok=True)
    base = f"{settings.endpoint}/_aws/execute-api/{outputs['ApiId']}/local"
    (ROOT / ".local/outputs.json").write_text(json.dumps({**outputs, "HealthUrl": url,
        "VersionedHealthUrl": base + "/api/v1/health", "ReadinessUrl": base + "/api/v1/ready",
        "PackageKey": package_key}, indent=2))
    print(f"Infraestructura creada. Verificar integración con: curl --fail {url}")


if __name__ == "__main__":
    main()
