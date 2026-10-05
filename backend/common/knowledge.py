"""Sincronización incremental de la base de conocimiento, compartida por el evento y el endpoint manual (ADR-010)."""

from dataclasses import asdict, dataclass

import boto3

_ACTIVE_STATUSES = ("STARTING", "IN_PROGRESS", "STOPPING")

_client = None


def _bedrock_agent():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agent")
    return _client


@dataclass
class SyncResult:
    started: bool
    ingestionJobId: str | None
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


def start_sync_if_idle(knowledge_base_id: str, data_source_id: str) -> SyncResult:
    """Lanza una sincronización salvo que ya haya una en curso.

    Bedrock no admite dos sincronizaciones simultáneas sobre la misma fuente de datos.
    """
    client = _bedrock_agent()
    for status in _ACTIVE_STATUSES:
        running = client.list_ingestion_jobs(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
            filters=[{"attribute": "STATUS", "operator": "EQ", "values": [status]}],
            maxResults=1,
        ).get("ingestionJobSummaries", [])
        if running:
            return SyncResult(
                started=False,
                ingestionJobId=running[0]["ingestionJobId"],
                message="Ya hay una sincronización en curso; no se lanzó otra.",
            )

    job = client.start_ingestion_job(knowledgeBaseId=knowledge_base_id, dataSourceId=data_source_id)["ingestionJob"]
    return SyncResult(started=True, ingestionJobId=job["ingestionJobId"], message="Sincronización iniciada.")
