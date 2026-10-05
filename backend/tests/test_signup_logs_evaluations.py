"""Registro restringido (ADR-007), visor de logs (ADR-037) y evaluaciones (pasos 17-19)."""

import json
import time
from decimal import Decimal

import boto3
import pytest
from apitest import api_event, body_of, put_parameter
from botocore.exceptions import ParamValidationError

from api import get_log_events, list_evaluations, list_log_groups
from common import evaluations, log_viewer
from triggers import pre_signup

ALLOWLIST = {"emails": ["Persona@Externa.com"], "domains": ["@empresa.com"]}


@pytest.mark.parametrize(
    ("email", "allowed"),
    [
        ("persona@externa.com", True),
        ("alguien@empresa.com", True),
        ("ALGUIEN@EMPRESA.COM", True),
        ("alguien@empresa.com.evil.io", False),
        ("intruso@otra.com", False),
        ("sin-arroba", False),
    ],
)
def test_allowlist(email, allowed):
    assert pre_signup.is_allowed(email, ALLOWLIST) is allowed


def test_allowlist_with_only_emails_admits_just_those_emails():
    # Solo correos y ningún dominio: únicamente esas personas se pueden registrar.
    allowlist = {"emails": ["camilo@correo.com"], "domains": []}
    assert pre_signup.is_allowed("Camilo@Correo.com", allowlist)
    assert not pre_signup.is_allowed("otra@correo.com", allowlist)


def test_pre_signup_rejects_unknown_email(monkeypatch, context):
    arn = boto3.client("secretsmanager").create_secret(Name="allowlist", SecretString=json.dumps(ALLOWLIST))["ARN"]
    monkeypatch.setenv("ALLOWLIST_SECRET_ARN", arn)
    event = {"triggerSource": "PreSignUp_SignUp", "request": {"userAttributes": {"email": "intruso@otra.com"}}}

    with pytest.raises(PermissionError):
        pre_signup.handler(event, context)

    event["request"]["userAttributes"]["email"] = "nueva@empresa.com"
    assert pre_signup.handler(event, context) is event


@pytest.fixture
def tagged_log_groups(monkeypatch):
    monkeypatch.setenv("LOG_TAG_FILTERS_PARAM", "/test/logs/tag-filters")
    put_parameter("/test/logs/tag-filters", json.dumps({"app": "rag"}))
    logs = boto3.client("logs")
    logs.create_log_group(logGroupName="/aws/lambda/app", tags={"app": "rag"})
    logs.create_log_group(logGroupName="/aws/lambda/ajeno", tags={"app": "otra"})
    logs.create_log_stream(logGroupName="/aws/lambda/app", logStreamName="s")
    logs.put_log_events(
        logGroupName="/aws/lambda/app",
        logStreamName="s",
        logEvents=[{"timestamp": int(time.time() * 1000) + i, "message": f"linea {i}\n"} for i in range(3)],
    )


def test_log_groups_fallback_filters_by_app_tags(tagged_log_groups, monkeypatch, context):
    # Simula un SDK de runtime que todavía no conoce el filtro logGroupTags de ListLogGroups.
    client = log_viewer.logs_client()

    def old_sdk(**_kwargs):
        raise ParamValidationError(report="Unknown parameter in input: logGroupTags")

    monkeypatch.setattr(client, "list_log_groups", old_sdk)

    response = list_log_groups.handler(api_event("GET", "/logs/groups"), context)
    assert [g["name"] for g in body_of(response)["logGroups"]] == ["/aws/lambda/app"]


def test_log_groups_use_tag_filter_when_available(tagged_log_groups, monkeypatch, context):
    calls = []

    def list_log_groups_api(**kwargs):
        calls.append(kwargs)
        return {"logGroups": [{"logGroupName": "/aws/lambda/app"}]}

    monkeypatch.setattr(log_viewer.logs_client(), "list_log_groups", list_log_groups_api)

    response = list_log_groups.handler(api_event("GET", "/logs/groups"), context)

    assert [g["name"] for g in body_of(response)["logGroups"]] == ["/aws/lambda/app"]
    assert calls[0]["logGroupTags"] == [{"key": "app", "values": ["rag"]}]


def test_foreign_log_group_is_not_readable(tagged_log_groups, context):
    group_id = log_viewer.log_group_id("/aws/lambda/ajeno")
    event = api_event("GET", f"/logs/groups/{group_id}/events", None, {"logGroupId": group_id})
    event["resource"] = "/logs/groups/{logGroupId}/events"
    assert get_log_events.handler(event, context)["statusCode"] == 404


def test_has_app_tags_requires_every_tag():
    assert log_viewer.has_app_tags({"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "2"})
    assert not log_viewer.has_app_tags({"a": "1"}, {"a": "1", "b": "2"})


def test_format_event_is_plain_text():
    line = get_log_events.format_event({"timestamp": 0, "message": "hola\n"})
    assert line == "1970-01-01T00:00:00.000+00:00 hola"


def test_dynamodb_decimals_become_json_numbers():
    assert evaluations.plain({"a": Decimal("1"), "b": [Decimal("0.5")]}) == {"a": 1, "b": [0.5]}


def test_list_evaluations_newest_first_without_results(monkeypatch, context):
    monkeypatch.setenv("EVALUATIONS_TABLE_NAME", "evaluaciones-test")
    boto3.client("dynamodb").create_table(
        TableName="evaluaciones-test",
        KeySchema=[{"AttributeName": "evaluationId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "evaluationId", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    table = boto3.resource("dynamodb").Table("evaluaciones-test")
    table.put_item(Item={"evaluationId": "a", "status": "COMPLETED", "createdAt": "2026-01-01", "results": ["x"]})
    table.put_item(Item={"evaluationId": "b", "status": "RUNNING", "createdAt": "2026-02-01"})

    items = body_of(list_evaluations.handler(api_event("GET", "/evaluations"), context))["evaluations"]

    assert [item["evaluationId"] for item in items] == ["b", "a"]
    assert all("results" not in item for item in items)


def test_app_log_group_events_are_returned_as_text(tagged_log_groups, context):
    event = api_event(
        "GET",
        f"/logs/groups/{log_viewer.log_group_id('/aws/lambda/app')}/events",
        None,
        {"logGroupId": log_viewer.log_group_id("/aws/lambda/app")},
        {"hours": "168", "limit": "2"},
    )
    event["resource"] = "/logs/groups/{logGroupId}/events"

    response = get_log_events.handler(event, context)

    assert response["statusCode"] == 200
    assert response["multiValueHeaders"]["Content-Type"] == ["text/plain"]
    # Se conservan los eventos más recientes cuando hay más que el límite.
    assert response["body"].splitlines()[-1].endswith("linea 2")
    assert len(response["body"].splitlines()) == 2


def test_log_group_id_round_trips_and_is_path_safe():
    name = "/aws/vendedlogs/bedrock-agentcore/rag-agentico-swarm"
    group_id = log_viewer.log_group_id(name)
    assert "/" not in group_id and "%" not in group_id and "=" not in group_id
    assert log_viewer.log_group_name(group_id) == name
    assert log_viewer.log_group_name("no*valido") is None
