"""Reconocimiento de hallazgos de cdk-nag con la API nativa de validaciones de CDK (ADR-034).

Todo reconocimiento lleva una razón específica. Los comodines de IAM se reconocen por hallazgo
exacto, calculado igual que la regla AwsSolutions-IAM5 de cdk-nag, y solo en los constructs que se
revisaron uno por uno.
"""

import json

import jsii
from aws_cdk import Acknowledgment, Aspects, IAspect, Stack, Validations
from aws_cdk import aws_iam as iam
from constructs import IConstruct

LAMBDA_BASIC_EXECUTION_ROLE = (
    "AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole]"
)

# Funciones singleton que CDK crea por dentro (custom resources y BucketDeployment).
_CDK_INTERNAL_PREFIXES = (
    "AWS679f53fac002430cb0da5b7982bd2287",
    "Custom::CDKBucketDeployment",
    "BucketNotificationsHandler",
    "Custom::S3AutoDeleteObjectsCustomResourceProvider",
    "LogRetention",
)


def acknowledge(scope: IConstruct, rule_id: str, reason: str) -> None:
    """Reconoce una regla en `scope` y sus hijos."""
    Validations.of(scope).acknowledge(Acknowledgment(id=rule_id, reason=reason))


def _flatten(node) -> str:
    """Equivalente de flattenCfnReference de cdk-nag."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node.replace("${", "<").replace("}", ">")
    if isinstance(node, dict):
        if "Fn::Join" in node:
            delimiter, items = node["Fn::Join"]
            return delimiter.join(_flatten(item) for item in items)
        if "Fn::Sub" in node:
            return _flatten(node["Fn::Sub"])
        if "Fn::GetAtt" in node:
            resource, attribute = node["Fn::GetAtt"]
            return f"<{_flatten(resource)}.{_flatten(attribute)}>"
        if "Fn::ImportValue" in node:
            return _flatten(node["Fn::ImportValue"])
        if "Ref" in node:
            return f"<{_flatten(node['Ref'])}>"
    return json.dumps(node, separators=(",", ":"))


def _as_list(value) -> list:
    return value if isinstance(value, list) else [value]


def wildcard_findings(policy_document: dict) -> list[str]:
    """Hallazgos de AwsSolutions-IAM5 para un documento de política ya resuelto."""
    findings: list[str] = []
    for statement in policy_document.get("Statement", []):
        if statement.get("Effect") != "Allow":
            continue
        for action in _as_list(statement.get("Action", [])):
            if "*" in action:
                findings.append(f"Action::{action}")
        for resource in _as_list(statement.get("Resource", [])):
            flat = _flatten(resource)
            if "*" in flat:
                findings.append(f"Resource::{flat}")
    return list(dict.fromkeys(findings))


@jsii.implements(IAspect)
class _AcknowledgeWildcards:
    def __init__(self, reason: str) -> None:
        self._reason = reason

    def visit(self, node: IConstruct) -> None:
        if isinstance(node, iam.CfnPolicy):
            documents = [node.policy_document]
        elif isinstance(node, iam.CfnRole):
            documents = [policy.policy_document for policy in (Stack.of(node).resolve(node.policies) or [])]
        else:
            return
        stack = Stack.of(node)
        for document in documents:
            for finding in wildcard_findings(stack.resolve(document)):
                acknowledge(node, f"AwsSolutions-IAM5[{finding}]", self._reason)


def acknowledge_wildcards(scope: IConstruct, reason: str) -> None:
    """Reconoce los comodines de IAM de las políticas dentro de `scope`, revisadas a mano.

    Se calculan al sintetizar, porque los ARNs dependen de IDs lógicos y de la cuenta.
    """
    Aspects.of(scope).add(_AcknowledgeWildcards(reason))


def acknowledge_cdk_internals(stack: Stack) -> None:
    """Funciones que CDK crea por dentro para custom resources y BucketDeployment.

    No se pueden configurar (runtime, memoria, DLQ, rol), así que sus hallazgos se reconocen.
    """
    reason = "Función interna de CDK para un custom resource o BucketDeployment; su configuración no es editable."
    for child in stack.node.children:
        if not child.node.id.startswith(_CDK_INTERNAL_PREFIXES):
            continue
        for rule in (
            LAMBDA_BASIC_EXECUTION_ROLE,
            "AwsSolutions-L1",
            "Serverless-LambdaDLQ",
            "Serverless-LambdaLatestVersion",
            "Serverless-LambdaDefaultMemorySize",
            "Serverless-LambdaTracing",
        ):
            acknowledge(child, rule, reason)
        acknowledge_wildcards(child, reason)
