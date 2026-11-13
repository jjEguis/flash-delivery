"""Regresión: el entorno local debe poder provisionarse sin cdk bootstrap."""
import json


def test_template_has_no_bootstrap_dependency(monkeypatch):
    # Evita depender de permisos de la caché global del usuario durante la prueba.
    monkeypatch.setenv("JSII_RUNTIME_PACKAGE_CACHE", "disabled")
    from infrastructure.cdk.app import synthesize

    template = synthesize("backend/test-package.zip")
    serialized = json.dumps(template)
    assert "BootstrapVersion" not in template.get("Parameters", {})
    assert "/cdk-bootstrap/" not in serialized
    assert "CheckBootstrapVersion" not in template.get("Rules", {})
    assert "AWS::SSM::Parameter::Value" not in serialized
    functions = [resource["Properties"] for resource in template["Resources"].values()
                 if resource["Type"] == "AWS::Lambda::Function"]
    assert len(functions) == 2
    by_name = {function["FunctionName"]: function for function in functions}
    assert "ZipFile" in by_name["flashdelivery-health"]["Code"]
    ready = by_name["flashdelivery-readiness"]
    assert ready["Handler"] == "backend.readiness.handler"
    assert ready["Code"]["S3Bucket"] == "flashdelivery-local-assets"
    assert ready["Code"]["S3Key"] == "backend/test-package.zip"
    assert ready["Environment"]["Variables"]["REDIS_HOST"] == "redis"
