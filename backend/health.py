"""Sonda de ejecución, no comprueba dependencias ni implementa negocio."""
import json


def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"service": "flashdelivery", "status": "ok", "environment": "local"}),
    }
