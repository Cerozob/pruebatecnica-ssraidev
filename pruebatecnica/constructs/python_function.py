"""Lambda en Python con Powertools, rol propio y log group gestionado por CDK (ADR-003, ADR-028)."""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_ssm as ssm
from constructs import Construct

from pruebatecnica.constructs.nag import acknowledge

# Parámetro público que publica Powertools con el ARN de la última versión de su layer.
POWERTOOLS_LAYER_PARAMETER = "/aws/service/powertools/python/arm64/python3.14/latest"

_RETENTION = {
    1: logs.RetentionDays.ONE_DAY,
    3: logs.RetentionDays.THREE_DAYS,
    5: logs.RetentionDays.FIVE_DAYS,
    7: logs.RetentionDays.ONE_WEEK,
    14: logs.RetentionDays.TWO_WEEKS,
    30: logs.RetentionDays.ONE_MONTH,
    60: logs.RetentionDays.TWO_MONTHS,
    90: logs.RetentionDays.THREE_MONTHS,
    180: logs.RetentionDays.SIX_MONTHS,
    365: logs.RetentionDays.ONE_YEAR,
}


def retention(days: int) -> logs.RetentionDays:
    if days not in _RETENTION:
        raise ValueError(f"logs.retention_days debe ser uno de {sorted(_RETENTION)}")
    return _RETENTION[days]


def powertools_layer(scope: Construct) -> lambda_.ILayerVersion:
    """Layer de Powertools, uno por stack, resuelto desde SSM en tiempo de despliegue."""
    stack = Stack.of(scope)
    existing = stack.node.try_find_child("PowertoolsLayer")
    if existing is not None:
        return existing  # type: ignore[return-value]
    arn = ssm.StringParameter.value_for_string_parameter(stack, POWERTOOLS_LAYER_PARAMETER)
    return lambda_.LayerVersion.from_layer_version_arn(stack, "PowertoolsLayer", arn)


class PythonFunction(Construct):
    """Función Lambda ARM64 con Powertools.

    Cada función tiene su propio rol con permisos solo sobre su log group, en lugar de la
    política administrada AWSLambdaBasicExecutionRole, que da acceso a todos los log groups.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        code: lambda_.Code,
        handler: str,
        service_name: str,
        description: str,
        log_retention_days: int,
        environment: dict[str, str] | None = None,
        timeout: Duration | None = None,
        memory_size: int = 512,
        dead_letter_queue: sqs.IQueue | None = None,
    ) -> None:
        super().__init__(scope, construct_id)

        self.log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=retention(log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.role = iam.Role(
            self,
            "Role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description=f"Rol de ejecución de {service_name}",
        )
        self.role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[self.log_group.log_group_arn],
            )
        )

        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_14,
            architecture=lambda_.Architecture.ARM_64,
            code=code,
            handler=handler,
            description=description,
            role=self.role,
            log_group=self.log_group,
            logging_format=lambda_.LoggingFormat.JSON,
            timeout=timeout or Duration.seconds(30),
            memory_size=memory_size,
            layers=[powertools_layer(self)],
            dead_letter_queue=dead_letter_queue,
            environment={
                "POWERTOOLS_SERVICE_NAME": service_name,
                "POWERTOOLS_LOG_LEVEL": "INFO",
                **(environment or {}),
            },
        )

        acknowledge(
            self,
            "Serverless-LambdaTracing",
            "X-Ray queda como mejora futura de observabilidad (ADR-039); las trazas de los agentes van por AgentCore.",
        )
        if dead_letter_queue is None:
            acknowledge(
                self,
                "Serverless-LambdaDLQ",
                "Invocación síncrona (API Gateway, Cognito o el gateway MCP): el error vuelve al llamador.",
            )
