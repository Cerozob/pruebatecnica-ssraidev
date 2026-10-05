"""Utilidades compartidas por las pruebas de los Lambdas."""

import json
from dataclasses import dataclass

import boto3


@dataclass
class LambdaContext:
    function_name: str = "test"
    memory_limit_in_mb: int = 128
    invoked_function_arn: str = "arn:aws:lambda:us-east-1:123456789012:function:test"
    aws_request_id: str = "request-id"


USER_ID = "usuario-1"


def api_event(
    method: str,
    path: str,
    body: dict | None = None,
    path_parameters: dict | None = None,
    query=None,
    user_id: str = USER_ID,
):
    """Evento de API Gateway REST como lo entrega el proxy de Lambda."""
    return {
        "resource": path,
        "path": path,
        "httpMethod": method,
        "headers": {"Content-Type": "application/json", "Origin": "http://localhost:5173"},
        "multiValueHeaders": {},
        "queryStringParameters": query,
        "multiValueQueryStringParameters": {k: [v] for k, v in (query or {}).items()} or None,
        "pathParameters": path_parameters,
        "stageVariables": None,
        "requestContext": {
            "resourcePath": path,
            "httpMethod": method,
            "path": f"/api{path}",
            "stage": "api",
            "requestId": "request-id",
            "identity": {"sourceIp": "127.0.0.1"},
            # Claims que agrega el authorizer de Cognito.
            "authorizer": {"claims": {"sub": user_id, "email": f"{user_id}@empresa.com"}},
        },
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def body_of(response: dict):
    return json.loads(response["body"]) if response.get("body") else None


def put_parameter(name: str, value: str) -> None:
    boto3.client("ssm").put_parameter(Name=name, Value=value, Type="String", Overwrite=True)
