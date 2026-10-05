"""Herramientas de solicitudes: modelo de ADR-042, niveles fijos de ADR-022 y sin borrado (ADR-021)."""

import importlib
import pkgutil

import boto3
import pytest

import tools
from common import requests_repo

TABLE = "solicitudes-test"


@pytest.fixture(autouse=True)
def requests_table(monkeypatch):
    monkeypatch.setenv("REQUESTS_TABLE_NAME", TABLE)
    boto3.client("dynamodb").create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )


def call(tool: str, event: dict, context) -> dict:
    return importlib.import_module(f"tools.{tool}").handler(event, context)


def test_create_applies_defaults(context):
    created = call("create_request", {"description": "La VPN no conecta"}, context)["request"]

    assert created["description"] == "La VPN no conecta"
    assert created["summary"] == ""
    assert created["priority"] == "unassigned"
    assert created["effort"] == "unassigned"
    assert created["status"] == "pending"
    # UUIDv7: la versión es el primer carácter del tercer grupo.
    assert created["id"].split("-")[2][0] == "7"


def test_create_requires_description(context):
    assert "obligatorio" in call("create_request", {"description": "  "}, context)["error"]


def test_get_unknown_request_returns_error_for_agent(context):
    assert "No existe" in call("get_request", {"id": "nope"}, context)["error"]


def test_priority_and_effort_only_accept_fixed_levels(context):
    request_id = call("create_request", {"description": "Reporte lento"}, context)["request"]["id"]

    assert call("update_request_priority", {"id": request_id, "priority": "HIGH"}, context)["request"]["priority"] == (
        "high"
    )
    assert (
        "Valores permitidos"
        in call("update_request_priority", {"id": request_id, "priority": "urgente"}, context)["error"]
    )
    assert "Valores permitidos" in call("update_request_effort", {"id": request_id, "effort": "xl"}, context)["error"]


def test_status_accepts_only_known_values(context):
    request_id = call("create_request", {"description": "Alta de usuario"}, context)["request"]["id"]

    updated = call("update_request_status", {"id": request_id, "status": "in progress"}, context)["request"]
    assert updated["status"] == "in progress"
    assert "error" in call("update_request_status", {"id": request_id, "status": "cancelled"}, context)


def test_update_does_not_create_missing_requests(context):
    result = call("update_request_status", {"id": "no-existe", "status": "done"}, context)

    assert "No existe" in result["error"]
    assert boto3.resource("dynamodb").Table(TABLE).scan()["Count"] == 0


def test_summary_must_differ_from_description(context):
    request_id = call("create_request", {"description": "Factura sin enviar"}, context)["request"]["id"]

    assert (
        "distinto"
        in call("update_request_summary", {"id": request_id, "summary": "Factura sin enviar"}, context)["error"]
    )
    updated = call("update_request_summary", {"id": request_id, "summary": "Facturación bloqueada"}, context)
    assert updated["request"]["summary"] == "Facturación bloqueada"


def test_list_filters_by_status_in_creation_order(context):
    first = call("create_request", {"description": "Uno"}, context)["request"]["id"]
    second = call("create_request", {"description": "Dos"}, context)["request"]["id"]
    call("update_request_status", {"id": second, "status": "done"}, context)

    assert [r["id"] for r in call("list_requests", {}, context)["requests"]] == [first, second]
    done = call("list_requests", {"status": "done"}, context)
    assert done["count"] == 1 and done["requests"][0]["id"] == second


def test_there_is_no_delete_tool():
    names = [module.name for module in pkgutil.iter_modules(tools.__path__)]
    assert not any("delete" in name or "remove" in name for name in names)
    assert not any("delete" in name for name in dir(requests_repo))
