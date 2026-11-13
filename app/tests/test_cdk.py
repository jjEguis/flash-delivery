"""Regresión: el entorno local debe poder provisionarse sin cdk bootstrap."""
import json

from infra.routes import ROUTES
from lambdas.shared.config.settings import ROOT


def test_template_has_no_bootstrap_dependency(monkeypatch):
    # Evita depender de permisos de la caché global del usuario durante la prueba.
    monkeypatch.setenv("JSII_RUNTIME_PACKAGE_CACHE", "disabled")
    from infra.app import synthesize

    template = synthesize("lambdas/test-package.zip")
    serialized = json.dumps(template)
    assert "BootstrapVersion" not in template.get("Parameters", {})
    assert "/cdk-bootstrap/" not in serialized
    assert "CheckBootstrapVersion" not in template.get("Rules", {})
    assert "AWS::SSM::Parameter::Value" not in serialized
    resources = template["Resources"].values()
    functions = [r["Properties"] for r in resources if r["Type"] == "AWS::Lambda::Function"]
    implemented = [m for m in ROUTES if (ROOT / "lambdas" / m / "handler.py").exists()]
    assert len(functions) == 2 + len(implemented)
    by_name = {function["FunctionName"]: function for function in functions}
    assert "ZipFile" in by_name["flashdelivery-health"]["Code"]
    ready = by_name["flashdelivery-readiness"]
    assert ready["Handler"] == "lambdas.readiness.handler.main"
    assert ready["Code"]["S3Bucket"] == "flashdelivery-local-assets"
    assert ready["Code"]["S3Key"] == "lambdas/test-package.zip"
    assert ready["Environment"]["Variables"]["REDIS_HOST"] == "redis"
    for module in implemented:
        function = by_name[f"flashdelivery-{module}"]
        assert function["Handler"] == f"lambdas.{module}.handler.main"
        assert function["Code"]["S3Key"] == "lambdas/test-package.zip"
        assert {"DEV_AUTH_SECRET", "TRACKING_TOKEN_KEY", "ZONES"} <= set(function["Environment"]["Variables"])
    route_keys = {r["Properties"]["RouteKey"] for r in resources if r["Type"] == "AWS::ApiGatewayV2::Route"}
    expected = {route for module in implemented for route in ROUTES[module]}
    assert expected <= route_keys
    assert {"GET /health", "GET /api/v1/health", "GET /api/v1/ready"} <= route_keys
