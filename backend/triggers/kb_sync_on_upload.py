"""Sincroniza la base de conocimiento cuando EventBridge informa un cambio en el bucket de documentos (pasos 6-7)."""

from aws_lambda_powertools import Logger

from common.knowledge import start_sync_if_idle
from common.settings import param

logger = Logger()


@logger.inject_lambda_context
def handler(event, context):
    detail = event.get("detail", {})
    logger.info(
        "Cambio en el bucket de documentos",
        extra={"detail_type": event.get("detail-type"), "key": detail.get("object", {}).get("key")},
    )
    result = start_sync_if_idle(param("KNOWLEDGE_BASE_ID_PARAM"), param("DATA_SOURCE_ID_PARAM"))
    logger.info(result.message, extra={"ingestion_job_id": result.ingestionJobId, "started": result.started})
    return result.to_dict()
