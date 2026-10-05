"""POST /conversations/{conversationId}/messages: mensaje siguiente de una conversación (paso 9, ADR-018)."""

from typing import Annotated

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.event_handler.openapi.params import Path
from aws_lambda_powertools.logging import correlation_paths
from pydantic import BaseModel, Field

from common import conversations
from common.auth import current_user_id
from common.chat import continue_conversation
from common.conversations import SESSION_ID_PATTERN
from common.http import build_resolver

logger = Logger()
app = build_resolver()


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000, description="Mensaje del usuario")


@app.post("/conversations/<conversationId>/messages")
def send_message(
    conversationId: Annotated[str, Path(pattern=SESSION_ID_PATTERN)], body: MessageRequest
) -> tuple[dict, int]:
    conversation_id = conversationId
    user_id = current_user_id(app)
    logger.append_keys(conversation_id=conversation_id)
    # Solo se continúa una sesión que el backend creó para este usuario.
    if conversations.get_meta(conversation_id, user_id) is None:
        raise NotFoundError("La conversación no existe.")
    return continue_conversation(conversation_id, user_id, body.content), 200


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
