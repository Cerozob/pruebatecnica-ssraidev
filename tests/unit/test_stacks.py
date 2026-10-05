"""Síntesis de todos los stacks con cdk-nag y verificación de las decisiones de arquitectura."""

import json

import aws_cdk as cdk
import pytest
from aws_cdk import assertions
from cdk_nag import AwsSolutionsChecks, ServerlessChecks

from pruebatecnica.app_builder import build_app
from pruebatecnica.config import ROOT_DIR, parse_config

CONFIG = parse_config(json.loads((ROOT_DIR / "config.json.example").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def stacks():
    # Sin bundling: la prueba no compila el frontend ni construye imágenes.
    app = cdk.App(context={"aws:cdk:bundling-stacks": []})
    built = build_app(app, CONFIG)
    cdk.Validations.of(app).add_plugins(AwsSolutionsChecks(app), ServerlessChecks(app))
    # Falla si cdk-nag reporta un hallazgo sin reconocer.
    app.synth()
    return {name: assertions.Template.from_stack(stack) for name, stack in built.items()}


def resources(template, type_):
    return template.find_resources(type_)


def test_all_stacks_synthesize_clean_with_cdk_nag(stacks):
    assert len(stacks) == 8


def test_knowledge_base_is_managed(stacks):
    stacks["knowledge"].has_resource_properties(
        "AWS::Bedrock::KnowledgeBase",
        {
            "KnowledgeBaseConfiguration": {
                "Type": "MANAGED",
                "ManagedKnowledgeBaseConfiguration": {"EmbeddingModelType": "MANAGED"},
            }
        },
    )


def test_guardrail_only_filters_prompt_attacks(stacks):
    guardrail = next(iter(resources(stacks["agents"], "AWS::Bedrock::Guardrail").values()))["Properties"]
    filters = guardrail["ContentPolicyConfig"]["FiltersConfig"]
    assert [f["Type"] for f in filters] == ["PROMPT_ATTACK"]
    assert (
        set(guardrail) & {"SensitiveInformationPolicyConfig", "TopicPolicyConfig", "ContextualGroundingPolicyConfig"}
        == set()
    )


def test_no_policy_allows_deleting_requests(stacks):
    # ADR-021: ningún rol puede borrar elementos de ninguna tabla de la solución.
    for template in stacks.values():
        for policy in resources(template, "AWS::IAM::Policy").values():
            assert "dynamodb:DeleteItem" not in json.dumps(policy)
            assert "dynamodb:*" not in json.dumps(policy)


def test_summary_tool_can_read_the_request(stacks):
    # La herramienta lee la descripción antes de guardar el resumen.
    policies = resources(stacks["agents"], "AWS::IAM::Policy").values()
    summary = [p for p in policies if "UpdateRequestSummary" in json.dumps(p["Properties"]["Roles"])]
    assert len(summary) == 1
    statements = summary[0]["Properties"]["PolicyDocument"]["Statement"]
    actions = {a for s in statements for a in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])}
    assert {"dynamodb:GetItem", "dynamodb:UpdateItem"} <= actions


def test_gateway_exposes_request_tools_kb_and_restricted_web_search(stacks):
    targets = resources(stacks["agents"], "AWS::BedrockAgentCore::GatewayTarget")
    assert len(targets) == 9
    web = [t for t in targets.values() if t["Properties"]["Name"] == "busqueda-web"][0]
    configuration = web["Properties"]["TargetConfiguration"]["Mcp"]["Connector"]["Configurations"][0]
    assert configuration["ParameterValues"]["domainFilter"]["include"] == CONFIG.web_search_allowed_domains


def test_every_api_method_requires_cognito(stacks):
    methods = resources(stacks["api"], "AWS::ApiGateway::Method").values()
    secured = [m for m in methods if m["Properties"]["HttpMethod"] != "OPTIONS"]
    assert len(secured) == 10
    assert all(m["Properties"]["AuthorizationType"] == "COGNITO_USER_POOLS" for m in secured)


def test_project_lambdas_use_python_arm64_with_powertools(stacks):
    functions = [
        f["Properties"]
        for template in stacks.values()
        for f in resources(template, "AWS::Lambda::Function").values()
        if f["Properties"].get("Runtime", "").startswith("python3.14")
    ]
    assert len(functions) == 20
    assert all(f["Architectures"] == ["arm64"] for f in functions)
    assert all(f["Layers"] for f in functions)


def test_retained_log_groups_have_no_fixed_name(stacks):
    # Un nombre fijo en un recurso retenido haría fallar un nuevo despliegue después de cdk destroy.
    for template in stacks.values():
        for log_group in resources(template, "AWS::Logs::LogGroup").values():
            if log_group.get("DeletionPolicy") == "Retain":
                assert "LogGroupName" not in log_group["Properties"]


def test_cognito_has_admin_and_user_groups_with_default_assignment(stacks):
    groups = {g["Properties"]["GroupName"] for g in resources(stacks["auth"], "AWS::Cognito::UserPoolGroup").values()}
    assert groups == {"admins", "users"}
    pool = next(iter(resources(stacks["auth"], "AWS::Cognito::UserPool").values()))["Properties"]
    assert set(pool["LambdaConfig"]) >= {"PreSignUp", "PostConfirmation"}


def test_no_nat_gateways(stacks):
    for template in stacks.values():
        assert resources(template, "AWS::EC2::NatGateway") == {}


def test_sample_requests_are_seeded(stacks):
    seed = [r for r in resources(stacks["agents"], "Custom::AWS").values() if "BatchWriteItem" in json.dumps(r)]
    assert len(seed) == 1
