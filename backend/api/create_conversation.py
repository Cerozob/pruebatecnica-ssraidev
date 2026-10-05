"""POST /conversations: primer mensaje de una conversación nueva (pasos 8-9).

Se invoca el runtime sin sessionId: AgentCore crea la sesión y devuelve su id, que se devuelve como
`conversationId` para los mensajes siguientes.
"""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths
from pydantic import BaseModel, Field

from common.auth import current_user_id
from common.chat import start_conversation
from common.http import build_resolver

logger = Logger()
app = build_resolver()


class NewConversationRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000, description="Primer mensaje del usuario")


@app.post("/conversations")
def create_conversation(body: NewConversationRequest) -> tuple[dict, int]:
    return start_conversation(current_user_id(app), body.content), 201


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
