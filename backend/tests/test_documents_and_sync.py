"""Carga con URL prefirmada (ADR-009) y sincronización sin solapamientos (ADR-010)."""

import boto3
import pytest
from apitest import api_event, body_of, put_parameter
from botocore.stub import Stubber

from api import create_upload_url
from common import knowledge

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
