"""GET /conversations: conversaciones del usuario autenticado, la más reciente primero (paso 8)."""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from common import conversations
from common.auth import current_user_id
from common.http import build_resolver

logger = Logger()
app = build_resolver()


@app.get("/conversations")
def list_conversations() -> dict:
    return {"conversations": conversations.list_conversations(current_user_id(app))}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
