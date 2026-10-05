"""POST /knowledge-base/sync: sincronización manual de respaldo (paso 6, ADR-010)."""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from common.http import build_resolver
from common.knowledge import start_sync_if_idle
from common.settings import param

logger = Logger()
app = build_resolver()


@app.post("/knowledge-base/sync")
def sync_knowledge_base() -> tuple[dict, int]:
    result = start_sync_if_idle(param("KNOWLEDGE_BASE_ID_PARAM"), param("DATA_SOURCE_ID_PARAM"))
    logger.info(result.message, extra={"ingestion_job_id": result.ingestionJobId})
    return result.to_dict(), 202 if result.started else 200


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
