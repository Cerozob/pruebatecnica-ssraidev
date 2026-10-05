"""Historial de conversaciones para que cada usuario consulte las suyas desde el frontend (ADR-017).

El contexto que usa el agente no sale de aquí: lo administra AgentCore Runtime por sessionId. Esta tabla
solo registra los turnos para mostrarlos, y el id de cada conversación es el sessionId de AgentCore.

Modelo de una sola tabla:
* `sk = "META"`: datos de la conversación; `userId` y `updatedAt` alimentan el índice `byUser`.
* `sk = "MSG#<createdAt>#<messageId>"`: un mensaje; el orden de `sk` es el orden cronológico.
"""

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from common.ids import new_id, now_iso
from common.settings import env

TITLE_LENGTH = 80
# runtimeSessionId de AgentCore: entre 33 y 256 caracteres; el formato exacto lo decide el servicio.
SESSION_ID_PATTERN = r"^[^/\s]{33,256}$"

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(env("CONVERSATIONS_TABLE_NAME"))
    return _table


def _message_item(conversation_id: str, role: str, content: str, **extra: Any) -> dict:
    created_at = now_iso()
    message_id = new_id()
    item = {
        "conversationId": conversation_id,
        "sk": f"MSG#{created_at}#{message_id}",
        "messageId": message_id,
        "role": role,
        "content": content,
        "createdAt": created_at,
    }
    item.update({key: value for key, value in extra.items() if value is not None})
    return item


def _public_message(item: dict) -> dict:
    hidden = {"conversationId", "sk"}
    return {key: value for key, value in item.items() if key not in hidden}


def get_meta(conversation_id: str, user_id: str) -> dict | None:
    """Datos de la conversación, solo si pertenece al usuario."""
    item = table().get_item(Key={"conversationId": conversation_id, "sk": "META"}).get("Item")
    return item if item and item.get("userId") == user_id else None


def create_conversation(conversation_id: str, user_id: str, first_message: str) -> dict:
    timestamp = now_iso()
    item = {
        "conversationId": conversation_id,
        "sk": "META",
        "userId": user_id,
        "title": " ".join(first_message.split())[:TITLE_LENGTH],
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    table().put_item(Item=item, ConditionExpression="attribute_not_exists(conversationId)")
    return item


def touch_conversation(conversation_id: str) -> None:
    table().update_item(
        Key={"conversationId": conversation_id, "sk": "META"},
        UpdateExpression="SET updatedAt = :now",
        ExpressionAttributeValues={":now": now_iso()},
    )


def add_message(conversation_id: str, role: str, content: str, **extra: Any) -> dict:
    item = _message_item(conversation_id, role, content, **extra)
    table().put_item(Item=item)
    return _public_message(item)


def list_messages(conversation_id: str) -> list[dict]:
    items: list[dict] = []
    kwargs = {"KeyConditionExpression": Key("conversationId").eq(conversation_id) & Key("sk").begins_with("MSG#")}
    while True:
        page = table().query(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return [_public_message(item) for item in items]
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def list_conversations(user_id: str, limit: int = 50) -> list[dict]:
    page = table().query(
        IndexName="byUser",
        KeyConditionExpression=Key("userId").eq(user_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [
        {
            "conversationId": item["conversationId"],
            "title": item.get("title", ""),
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt"),
        }
        for item in page.get("Items", [])
    ]
