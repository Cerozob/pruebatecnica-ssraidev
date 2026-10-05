"""Sincroniza la base de conocimiento cuando cambia el bucket de documentos (pasos 6-7, ADR-010).

EventBridge deja cada cambio del bucket en una cola de SQS y este Lambda los procesa por lotes. Si hay una
sincronización en curso que empezó antes del cambio más reciente del lote, el lote falla y vuelve a la cola
tras el tiempo de visibilidad; así ningún archivo subido durante una sincronización queda sin indexar.
"""

import json
from datetime import datetime

from aws_lambda_powertools import Logger

from common.knowledge import start_sync_if_idle
from common.settings import param

logger = Logger()


def latest_change(records: list[dict]) -> datetime:
    """Hora del cambio más reciente del lote, tomada del evento de EventBridge de cada mensaje."""
    return max(datetime.fromisoformat(json.loads(record["body"])["time"].replace("Z", "+00:00")) for record in records)


@logger.inject_lambda_context
def handler(event, context):
    records = event.get("Records", [])
    if not records:
        return {"started": False, "ingestionJobId": None, "message": "Lote vacío."}
    changed_at = latest_change(records)
    logger.info("Cambios en el bucket de documentos", extra={"changes": len(records), "latest": changed_at.isoformat()})
    # SyncPendingError no se captura: el lote vuelve a la cola y se reintenta más tarde.
    result = start_sync_if_idle(param("KNOWLEDGE_BASE_ID_PARAM"), param("DATA_SOURCE_ID_PARAM"), changed_at)
    logger.info(result.message, extra={"ingestion_job_id": result.ingestionJobId, "started": result.started})
    return result.to_dict()
