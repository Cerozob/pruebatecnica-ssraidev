"""GET /conversations/{conversationId}: historial de mensajes de una conversación (paso 8)."""

from typing import Annotated

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.event_handler.openapi.params import Path
from aws_lambda_powertools.logging import correlation_paths

from common import conversations
from common.auth import current_user_id
from common.conversations import SESSION_ID_PATTERN
from common.http import build_resolver

logger = Logger()
app = build_resolver()


@app.get("/conversations/<conversationId>")
def get_conversation(conversationId: Annotated[str, Path(pattern=SESSION_ID_PATTERN)]) -> dict:
    conversation_id = conversationId
    meta = conversations.get_meta(conversation_id, current_user_id(app))
    if meta is None:
        raise NotFoundError("La conversación no existe.")
    return {
        "conversationId": conversation_id,
        "title": meta.get("title", ""),
        "createdAt": meta.get("createdAt"),
        "updatedAt": meta.get("updatedAt"),
        "messages": conversations.list_messages(conversation_id),
    }


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
