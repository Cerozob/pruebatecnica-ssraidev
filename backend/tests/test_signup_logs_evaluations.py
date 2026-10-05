"""Registro restringido (ADR-007), visor de logs (ADR-037) y evaluaciones (pasos 17-19)."""

import json
import time
from decimal import Decimal

import boto3
import pytest
from apitest import api_event, body_of, put_parameter
from botocore.exceptions import ParamValidationError

from api import get_evaluation, get_log_events, list_evaluations, list_log_groups, start_evaluation
from common import evaluations, log_viewer
from triggers import post_confirmation, pre_signup

ADMINS = ["admins", "users"]
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

    response = list_log_groups.handler(api_event("GET", "/logs/groups", groups=ADMINS), context)
    assert [g["name"] for g in body_of(response)["logGroups"]] == ["/aws/lambda/app"]


def test_log_groups_use_tag_filter_when_available(tagged_log_groups, monkeypatch, context):
    calls = []

    def list_log_groups_api(**kwargs):
        calls.append(kwargs)
        return {"logGroups": [{"logGroupName": "/aws/lambda/app"}]}

    monkeypatch.setattr(log_viewer.logs_client(), "list_log_groups", list_log_groups_api)

    response = list_log_groups.handler(api_event("GET", "/logs/groups", groups=ADMINS), context)

    assert [g["name"] for g in body_of(response)["logGroups"]] == ["/aws/lambda/app"]
    assert calls[0]["logGroupTags"] == [{"key": "app", "values": ["rag"]}]


def test_foreign_log_group_is_not_readable(tagged_log_groups, context):
    group_id = log_viewer.log_group_id("/aws/lambda/ajeno")
    event = api_event("GET", f"/logs/groups/{group_id}/events", None, {"logGroupId": group_id}, groups=ADMINS)
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

    items = body_of(list_evaluations.handler(api_event("GET", "/evaluations", groups=ADMINS), context))["evaluations"]

    assert [item["evaluationId"] for item in items] == ["b", "a"]
    assert all("results" not in item for item in items)


def test_app_log_group_events_are_returned_as_text(tagged_log_groups, context):
    event = api_event(
        "GET",
        f"/logs/groups/{log_viewer.log_group_id('/aws/lambda/app')}/events",
        None,
        {"logGroupId": log_viewer.log_group_id("/aws/lambda/app")},
        {"hours": "168", "limit": "2"},
        groups=ADMINS,
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


@pytest.mark.parametrize("groups", [None, ["users"], ["administradores"]])
@pytest.mark.parametrize(
    ("module", "method", "path", "params"),
    [
        (list_log_groups, "GET", "/logs/groups", None),
        (get_log_events, "GET", "/logs/groups/{logGroupId}/events", {"logGroupId": "L2F3cy9sYW1iZGEvYXBw"}),
        (list_evaluations, "GET", "/evaluations", None),
        (start_evaluation, "POST", "/evaluations", None),
        (
            get_evaluation,
            "GET",
            "/evaluations/{evaluationId}",
            {"evaluationId": "0199a8a0-0000-7000-8000-000000000000"},
        ),
    ],
)
def test_logs_and_evaluations_are_admin_only(module, method, path, params, groups, context):
    # ADR-043: sin el grupo de administradores la API responde 403, antes de tocar cualquier recurso.
    event = api_event(method, path, None, params, groups=groups)
    if params:
        concrete = path
        for key, value in params.items():
            concrete = concrete.replace("{" + key + "}", value)
        event["path"] = concrete
    response = module.handler(event, context)
    assert response["statusCode"] == 403


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("admins", {"admins"}),
        ("admins,users", {"admins", "users"}),
        ("[admins users]", {"admins", "users"}),
        ("", set()),
    ],
)
def test_group_claim_formats(raw, expected):
    from types import SimpleNamespace

    from common.auth import user_groups

    claims = {"sub": "x", "cognito:groups": raw}
    app = SimpleNamespace(
        current_event=SimpleNamespace(request_context=SimpleNamespace(authorizer=SimpleNamespace(claims=claims)))
    )
    assert user_groups(app) == expected


def test_post_confirmation_adds_new_users_to_the_users_group(monkeypatch, context):
    from botocore.stub import Stubber

    monkeypatch.setenv("DEFAULT_GROUP", "users")
    event = {"triggerSource": "PostConfirmation_ConfirmSignUp", "userPoolId": "us-east-1_abc", "userName": "nueva"}
    expected = {"UserPoolId": "us-east-1_abc", "Username": "nueva", "GroupName": "users"}

    with Stubber(post_confirmation._cognito_client()) as stubber:
        stubber.add_response("admin_add_user_to_group", {}, expected)
        assert post_confirmation.handler(event, context) is event
        stubber.assert_no_pending_responses()


def test_post_confirmation_ignores_password_resets(monkeypatch, context):
    monkeypatch.setenv("DEFAULT_GROUP", "users")
    event = {"triggerSource": "PostConfirmation_ConfirmForgotPassword", "userPoolId": "x", "userName": "y"}
    from botocore.stub import Stubber

    # Un Stubber sin respuestas falla ante cualquier llamada a Cognito.
    with Stubber(post_confirmation._cognito_client()):
        assert post_confirmation.handler(event, context) is event


@pytest.fixture
def evaluation_backend(monkeypatch):
    monkeypatch.setenv("EVALUATIONS_TABLE_NAME", "evaluaciones-test")
    boto3.client("dynamodb").create_table(
        TableName="evaluaciones-test",
        KeySchema=[{"AttributeName": "evaluationId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "evaluationId", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    arn = boto3.client("stepfunctions").create_state_machine(
        name="evaluacion",
        definition=json.dumps({"StartAt": "Fin", "States": {"Fin": {"Type": "Succeed"}}}),
        roleArn="arn:aws:iam::123456789012:role/sfn",
    )["stateMachineArn"]
    monkeypatch.setenv("EVALUATION_STATE_MACHINE_ARN", arn)
    monkeypatch.setattr(start_evaluation, "_sfn", None)
    return arn


def _start(context):
    return start_evaluation.handler(api_event("POST", "/evaluations", groups=ADMINS), context)


def test_only_one_evaluation_runs_at_a_time(evaluation_backend, context):
    first = _start(context)
    assert first["statusCode"] == 202
    # Un segundo clic, aunque pase el candado, ve la ejecución en curso.
    evaluations.table().update_item(
        Key={"evaluationId": evaluations.START_LOCK_ID},
        UpdateExpression="SET expiresAt = :past",
        ExpressionAttributeValues={":past": 0},
    )
    second = _start(context)
    assert second["statusCode"] == 409
    executions = boto3.client("stepfunctions").list_executions(stateMachineArn=evaluation_backend)["executions"]
    assert len(executions) == 1


def test_simultaneous_starts_are_blocked_by_the_lock(evaluation_backend, context):
    evaluations.table().put_item(Item={"evaluationId": evaluations.START_LOCK_ID, "expiresAt": int(time.time()) + 60})
    assert _start(context)["statusCode"] == 409
    assert boto3.client("stepfunctions").list_executions(stateMachineArn=evaluation_backend)["executions"] == []


def test_start_lock_is_not_listed_as_an_evaluation(evaluation_backend, context):
    assert _start(context)["statusCode"] == 202
    items = body_of(list_evaluations.handler(api_event("GET", "/evaluations", groups=ADMINS), context))["evaluations"]
    assert len(items) == 1 and items[0]["evaluationId"] != evaluations.START_LOCK_ID
