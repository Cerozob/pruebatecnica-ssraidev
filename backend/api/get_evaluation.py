"""GET /evaluations/{evaluationId}: progreso y resultados de una evaluación (paso 19)."""

from typing import Annotated
from uuid import UUID

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.event_handler.openapi.params import Path
from aws_lambda_powertools.logging import correlation_paths

from common import evaluations
from common.auth import require_admin
from common.http import build_resolver

logger = Logger()
app = build_resolver()


@app.get("/evaluations/<evaluationId>")
def get_evaluation(evaluationId: Annotated[UUID, Path()]) -> dict:
    require_admin(app)
    item = evaluations.table().get_item(Key={"evaluationId": str(evaluationId)}).get("Item")
    if item is None:
        raise NotFoundError("La evaluación no existe.")
    return {**evaluations.summarize(item), "results": evaluations.plain(item.get("results", []))}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
