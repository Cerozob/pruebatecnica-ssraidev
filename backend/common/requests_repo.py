"""Solicitudes: modelo de datos (ADR-042) y operaciones de las herramientas del agente (ADR-020 a ADR-022).

No existe ninguna operación de borrado (ADR-021).
"""

from functools import wraps

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from common.ids import new_id
from common.settings import env

logger = Logger()

LEVELS = ("low", "medium", "high")
STATUSES = ("pending", "in progress", "delayed", "done")
UNASSIGNED = "unassigned"
MAX_TEXT_LENGTH = 4000

_table = None


class ToolInputError(ValueError):
    """Entrada inválida: el mensaje se devuelve al agente para que corrija la llamada."""


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(env("REQUESTS_TABLE_NAME"))
    return _table


def require_text(event: dict, field: str) -> str:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ToolInputError(f"El campo '{field}' es obligatorio y debe ser texto.")
    if len(value) > MAX_TEXT_LENGTH:
        raise ToolInputError(f"El campo '{field}' no puede superar {MAX_TEXT_LENGTH} caracteres.")
    return value.strip()


def require_choice(event: dict, field: str, allowed: tuple[str, ...]) -> str:
    value = require_text(event, field).lower()
    if value not in allowed:
        raise ToolInputError(f"Valor inválido para '{field}': '{value}'. Valores permitidos: {', '.join(allowed)}.")
    return value


def tool_handler(func):
    """Convierte errores de validación y de solicitudes inexistentes en una respuesta para el agente."""

    @wraps(func)
    def wrapper(event, context):
        logger.info("Herramienta invocada", extra={"tool": func.__name__, "input": event})
        try:
            return func(event or {})
        except ToolInputError as error:
            return {"error": str(error)}

    return logger.inject_lambda_context(wrapper)


def create(description: str) -> dict:
    item = {
        "id": new_id(),
        "description": description,
        "summary": "",
        "priority": UNASSIGNED,
        "effort": UNASSIGNED,
        "status": "pending",
    }
    table().put_item(Item=item, ConditionExpression="attribute_not_exists(id)")
    return item


def get(request_id: str) -> dict:
    item = table().get_item(Key={"id": request_id}).get("Item")
    if item is None:
        raise ToolInputError(f"No existe una solicitud con id '{request_id}'.")
    return item


def list_all(status: str | None = None) -> list[dict]:
    kwargs = {"FilterExpression": Attr("status").eq(status)} if status else {}
    items: list[dict] = []
    while True:
        page = table().scan(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    # El id es UUIDv7: ordenarlo es ordenar por fecha de creación.
    return sorted(items, key=lambda item: item["id"])


def update_field(request_id: str, field: str, value: str) -> dict:
    try:
        return table().update_item(
            Key={"id": request_id},
            UpdateExpression="SET #field = :value",
            ConditionExpression="attribute_exists(id)",
            ExpressionAttributeNames={"#field": field},
            ExpressionAttributeValues={":value": value},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as error:
        if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ToolInputError(f"No existe una solicitud con id '{request_id}'.") from error
        raise
