"""Punto de entrada CDK; sin lookup ni llamadas a AWS durante la síntesis."""
from aws_cdk import App
from lambdas.shared.config.settings import ROOT, Settings
from infra.stack import FlashDeliveryStack


def synthesize(package_key="lambdas/not-built.zip"):
    app = App(outdir=str(ROOT / "cdk.out"), analytics_reporting=False)
    stack = FlashDeliveryStack(app, Settings.load(), package_key)
    return app.synth().get_stack_by_name(stack.stack_name).template


if __name__ == "__main__":
    synthesize()
