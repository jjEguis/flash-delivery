"""Síntesis sin lookup ni bootstrap CDK; paquete publicado por scripts.provision."""
from aws_cdk import App, Stack, CfnOutput, RemovalPolicy, BootstraplessSynthesizer
from aws_cdk import aws_dynamodb as dynamodb, aws_lambda as lambda_, aws_iam as iam
from aws_cdk import aws_apigatewayv2 as apigw
from backend.shared.config.settings import ROOT, Settings
from scripts.package_lambda import ASSET_BUCKET


def synthesize(package_key="backend/not-built.zip"):
    settings = Settings.load()
    app = App(outdir=str(ROOT / "cdk.out"), analytics_reporting=False)
    stack = Stack(app, "FlashDeliveryLocal", synthesizer=BootstraplessSynthesizer(), env={"account": "000000000000", "region": settings.region})
    table = dynamodb.Table(stack, "Table", table_name=settings.table_name,
        partition_key=dynamodb.Attribute(name="PK", type=dynamodb.AttributeType.STRING),
        sort_key=dynamodb.Attribute(name="SK", type=dynamodb.AttributeType.STRING),
        billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST, removal_policy=RemovalPolicy.RETAIN)
    for index in ("GSI1", "GSI2"):
        table.add_global_secondary_index(index_name=index,
            partition_key=dynamodb.Attribute(name=index+"PK", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name=index+"SK", type=dynamodb.AttributeType.STRING),
            projection_type=dynamodb.ProjectionType.ALL)
    role = iam.Role(stack, "HealthRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
    function = lambda_.CfnFunction(stack, "Health", function_name="flashdelivery-health",
        runtime="python3.12", handler="index.handler", role=role.role_arn,
        code=lambda_.CfnFunction.CodeProperty(zip_file=(ROOT / "backend/health.py").read_text()),
        timeout=5, memory_size=128)
    api = apigw.CfnApi(stack, "Api", name="flashdelivery-local", protocol_type="HTTP")
    integration = apigw.CfnIntegration(stack, "Integration", api_id=api.ref,
        integration_type="AWS_PROXY", integration_uri=function.attr_arn,
        integration_method="POST", payload_format_version="2.0")
    route = apigw.CfnRoute(stack, "HealthRoute", api_id=api.ref,
        route_key="GET /health", target="integrations/" + integration.ref)
    stage = apigw.CfnStage(stack, "Stage", api_id=api.ref, stage_name="local", auto_deploy=True)
    stage.add_dependency(route)
    lambda_.CfnPermission(stack, "InvokePermission", action="lambda:InvokeFunction",
        function_name=function.ref, principal="apigateway.amazonaws.com",
        source_arn=f"arn:aws:execute-api:{settings.region}:000000000000:{api.ref}/*/GET/health")
    ready_role = iam.Role(stack, "ReadinessRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"))
    table.grant(ready_role, "dynamodb:DescribeTable")
    ready = lambda_.CfnFunction(stack, "Readiness", function_name="flashdelivery-readiness",
        runtime="python3.12", handler="backend.readiness.handler", role=ready_role.role_arn,
        code=lambda_.CfnFunction.CodeProperty(s3_bucket=ASSET_BUCKET, s3_key=package_key),
        environment=lambda_.CfnFunction.EnvironmentProperty(variables={
            "ENVIRONMENT": "local", "AWS_ENDPOINT_URL": "http://ministack:4566",
            "AWS_EC2_METADATA_DISABLED": "true", "DYNAMODB_TABLE_NAME": settings.table_name,
            "REDIS_HOST": "redis", "REDIS_PORT": "6379",
            "CONNECT_TIMEOUT": str(settings.connect_timeout), "READ_TIMEOUT": str(settings.read_timeout),
        }), timeout=20, memory_size=256)
    ready_integration = apigw.CfnIntegration(stack, "ReadinessIntegration", api_id=api.ref,
        integration_type="AWS_PROXY", integration_uri=ready.attr_arn,
        integration_method="POST", payload_format_version="2.0")
    for name, path, target_function, target_integration in (
        ("VersionedHealth", "/api/v1/health", function, integration),
        ("Readiness", "/api/v1/ready", ready, ready_integration),
    ):
        extra_route = apigw.CfnRoute(stack, name + "Route", api_id=api.ref,
            route_key="GET " + path, target="integrations/" + target_integration.ref)
        stage.add_dependency(extra_route)
        lambda_.CfnPermission(stack, name + "Permission", action="lambda:InvokeFunction",
            function_name=target_function.ref, principal="apigateway.amazonaws.com",
            source_arn=f"arn:aws:execute-api:{settings.region}:000000000000:{api.ref}/*/GET{path}")
    CfnOutput(stack, "ApiId", value=api.ref)
    CfnOutput(stack, "TableName", value=table.table_name)
    return app.synth().get_stack_by_name(stack.stack_name).template


if __name__ == "__main__":
    synthesize()
