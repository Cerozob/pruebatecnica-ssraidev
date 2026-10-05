"""GET /evaluations: evaluaciones anteriores y su estado (paso 19)."""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from common import evaluations
from common.http import build_resolver

logger = Logger()
app = build_resolver()


@app.get("/evaluations")
def list_evaluations() -> dict:
    items: list[dict] = []
    # Pocas evaluaciones y sin resultados detallados: un Scan con proyección es suficiente.
    kwargs = {
        "ProjectionExpression": "evaluationId, #status, createdAt, startedAt, finishedAt, progress, summary, #error",
        "ExpressionAttributeNames": {"#status": "status", "#error": "error"},
    }
    while True:
        page = evaluations.table().scan(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    ordered = sorted(items, key=lambda item: item.get("createdAt", ""), reverse=True)
    return {"evaluations": [evaluations.summarize(item) for item in ordered]}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
