"""Carga con URL prefirmada (ADR-009) y sincronización sin solapamientos (ADR-010)."""

import json
from datetime import UTC, datetime

import boto3
import pytest
from apitest import api_event, body_of, put_parameter
from botocore.stub import Stubber

from api import create_upload_url
from common import knowledge
from triggers import kb_sync_on_upload

BUCKET = "documentos-test"


@pytest.fixture
def documents_bucket(monkeypatch):
    monkeypatch.setattr(create_upload_url, "_s3", None)
    monkeypatch.setenv("DOCUMENTS_BUCKET_PARAM", "/test/knowledge/documents-bucket")
    put_parameter("/test/knowledge/documents-bucket", BUCKET)
    boto3.client("s3").create_bucket(Bucket=BUCKET)


def request_upload(body: dict, context):
    return create_upload_url.handler(api_event("POST", "/documents/upload-url", body), context)


def test_upload_url_uses_safe_key_under_prefix(documents_bucket, context):
    response = request_upload(
        {"fileName": "../Informe Q3 (final).pdf", "contentType": "application/pdf", "size": 1024}, context
    )

    assert response["statusCode"] == 201
    body = body_of(response)
    assert body["key"].startswith("documentos/")
    assert body["key"].endswith("/Informe-Q3-final.pdf")
    assert BUCKET in body["uploadUrl"]


@pytest.mark.parametrize(
    "body",
    [
        {"fileName": "virus.exe", "contentType": "application/octet-stream", "size": 10},
        {"fileName": "grande.pdf", "contentType": "application/pdf", "size": 51 * 1024 * 1024},
        {"fileName": "vacio.pdf", "contentType": "application/pdf", "size": 0},
    ],
)
def test_upload_url_rejects_unsupported_files(body, documents_bucket, context):
    assert request_upload(body, context)["statusCode"] == 400


def test_safe_file_name_strips_paths_and_symbols():
    assert create_upload_url.safe_file_name("C:\\tmp\\Política de viajes.DOCX") == "Política-de-viajes.docx"
    assert create_upload_url.safe_file_name("../###.PDF") == "documento.pdf"


@pytest.fixture
def bedrock_agent(monkeypatch):
    client = boto3.client("bedrock-agent")
    monkeypatch.setattr(knowledge, "_client", client)
    with Stubber(client) as stubber:
        yield stubber


def _no_jobs(stubber, status):
    stubber.add_response(
        "list_ingestion_jobs",
        {"ingestionJobSummaries": []},
        {
            "knowledgeBaseId": "KB1",
            "dataSourceId": "DS1",
            "filters": [{"attribute": "STATUS", "operator": "EQ", "values": [status]}],
            "maxResults": 1,
        },
    )


def test_sync_skips_when_a_job_is_running(bedrock_agent):
    _no_jobs(bedrock_agent, "STARTING")
    bedrock_agent.add_response(
        "list_ingestion_jobs",
        {
            "ingestionJobSummaries": [
                {
                    "ingestionJobId": "JOB1",
                    "knowledgeBaseId": "KB1",
                    "dataSourceId": "DS1",
                    "status": "IN_PROGRESS",
                    "startedAt": "2026-10-04T00:00:00Z",
                    "updatedAt": "2026-10-04T00:00:00Z",
                }
            ]
        },
    )

    result = knowledge.start_sync_if_idle("KB1", "DS1")

    assert result.started is False
    assert result.ingestionJobId == "JOB1"
    bedrock_agent.assert_no_pending_responses()


def test_sync_starts_when_idle(bedrock_agent):
    for status in ("STARTING", "IN_PROGRESS", "STOPPING"):
        _no_jobs(bedrock_agent, status)
    bedrock_agent.add_response(
        "start_ingestion_job",
        {
            "ingestionJob": {
                "ingestionJobId": "JOB2",
                "knowledgeBaseId": "KB1",
                "dataSourceId": "DS1",
                "status": "STARTING",
                "startedAt": "2026-10-04T00:00:00Z",
                "updatedAt": "2026-10-04T00:00:00Z",
            }
        },
        {"knowledgeBaseId": "KB1", "dataSourceId": "DS1"},
    )

    result = knowledge.start_sync_if_idle("KB1", "DS1")

    assert result.started is True and result.ingestionJobId == "JOB2"


def test_csv_uploads_keep_their_extension():
    assert create_upload_url.safe_file_name("matches.CSV") == "matches.csv"


def _running_job(stubber, started_at):
    _no_jobs(stubber, "STARTING")
    stubber.add_response(
        "list_ingestion_jobs",
        {
            "ingestionJobSummaries": [
                {
                    "ingestionJobId": "JOB1",
                    "knowledgeBaseId": "KB1",
                    "dataSourceId": "DS1",
                    "status": "IN_PROGRESS",
                    "startedAt": started_at,
                    "updatedAt": started_at,
                }
            ]
        },
    )


def _sqs_event(*times):
    return {"Records": [{"body": json.dumps({"time": time, "detail": {}})} for time in times]}


@pytest.fixture
def sync_params(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_BASE_ID_PARAM", "/test/kb-id")
    monkeypatch.setenv("DATA_SOURCE_ID_PARAM", "/test/ds-id")
    put_parameter("/test/kb-id", "KB1")
    put_parameter("/test/ds-id", "DS1")


def test_upload_during_an_older_sync_is_retried(bedrock_agent, sync_params, context):
    # La sincronización en curso empezó antes de la carga: puede no incluir el archivo, así que el lote se reintenta.
    _running_job(bedrock_agent, datetime(2026, 10, 5, 10, 0, tzinfo=UTC))
    with pytest.raises(knowledge.SyncPendingError):
        kb_sync_on_upload.handler(_sqs_event("2026-10-05T09:59:00Z", "2026-10-05T10:01:00Z"), context)


def test_upload_covered_by_a_newer_sync_is_skipped(bedrock_agent, sync_params, context):
    _running_job(bedrock_agent, datetime(2026, 10, 5, 10, 5, tzinfo=UTC))
    result = kb_sync_on_upload.handler(_sqs_event("2026-10-05T10:01:00Z"), context)
    assert result["started"] is False and result["ingestionJobId"] == "JOB1"


def test_concurrent_start_is_retried(bedrock_agent, sync_params, context):
    for status in ("STARTING", "IN_PROGRESS", "STOPPING"):
        _no_jobs(bedrock_agent, status)
    bedrock_agent.add_client_error("start_ingestion_job", service_error_code="ConflictException", http_status_code=409)
    with pytest.raises(knowledge.SyncPendingError):
        kb_sync_on_upload.handler(_sqs_event("2026-10-05T10:01:00Z"), context)
