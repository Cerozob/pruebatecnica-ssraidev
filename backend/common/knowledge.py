"""Sincronización incremental de la base de conocimiento, lanzada por los eventos del bucket de documentos (ADR-010)."""

from dataclasses import asdict, dataclass
from datetime import datetime

import boto3

_ACTIVE_STATUSES = ("STARTING", "IN_PROGRESS", "STOPPING")

_client = None


def _bedrock_agent():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent")
    return _client


class SyncPendingError(Exception):
    """Hay una sincronización en curso que empezó antes del cambio: puede no incluirlo y hay que reintentar."""


@dataclass
class SyncResult:
    started: bool
    ingestionJobId: str | None
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def _active_job(client, knowledge_base_id: str, data_source_id: str) -> dict | None:
    for status in _ACTIVE_STATUSES:
        running = client.list_ingestion_jobs(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            filters=[{"attribute": "STATUS", "operator": "EQ", "values": [status]}],
            maxResults=1,
        ).get("ingestionJobSummaries", [])
        if running:
            return running[0]
    return None


def start_sync_if_idle(knowledge_base_id: str, data_source_id: str, changed_at: datetime | None = None) -> SyncResult:
    """Lanza una sincronización salvo que ya haya una en curso. Es idempotente: nunca lanza dos a la vez.

    Bedrock no admite dos sincronizaciones simultáneas sobre la misma fuente de datos. Con `changed_at` (la hora
    del cambio en el bucket), una sincronización en curso solo cubre el cambio si empezó después de él; si empezó
    antes, se lanza SyncPendingError para que el evento se reintente cuando termine y el archivo no se pierda.
    """
    client = _bedrock_agent()
    running = _active_job(client, knowledge_base_id, data_source_id)
    if running:
        if changed_at is not None and running["startedAt"] < changed_at:
            raise SyncPendingError(f"La sincronización {running['ingestionJobId']} empezó antes del cambio.")
        return SyncResult(
            started=False,
            ingestionJobId=running["ingestionJobId"],
            message="Ya hay una sincronización en curso; no se lanzó otra.",
        )

    try:
        job = client.start_ingestion_job(knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id)
    except client.exceptions.ConflictException as error:
        # Otra invocación la lanzó entre la consulta y este llamado.
        if changed_at is not None:
            raise SyncPendingError("Otra sincronización empezó al mismo tiempo.") from error
        return SyncResult(started=False, ingestionJobId=None, message="Ya hay una sincronización en curso.")
    job = job["ingestionJob"]
    return SyncResult(started=True, ingestionJobId=job["ingestionJobId"], message="Sincronización iniciada.")
