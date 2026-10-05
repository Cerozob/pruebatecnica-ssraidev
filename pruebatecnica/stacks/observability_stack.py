"""Observabilidad compartida: bucket de logs de acceso y registro de invocaciones de Bedrock (pasos 23-25)."""

from aws_cdk import Duration, RemovalPolicy, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import custom_resources as cr
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.nag import acknowledge
from pruebatecnica.constructs.python_function import retention

INVOCATION_LOGS_PREFIX = "invocaciones"


class ObservabilityStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: AppConfig, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Destino de los logs de acceso de los demás buckets (AwsSolutions-S1).
        self.access_logs_bucket = s3.Bucket(
            self,
            "AccessLogsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        acknowledge(
            self.access_logs_bucket,
            "AwsSolutions-S1",
            "Es el bucket destino de los logs de acceso; registrar sus propios accesos crearía un ciclo.",
        )

        self._model_invocation_logging(config)

    def _model_invocation_logging(self, config: AppConfig) -> None:
        """ADR-038: registro de invocaciones de modelos de Bedrock hacia CloudWatch y S3.

        El registro queda activo aunque se elimine el stack: el bucket, el log group y el rol se retienen
        y el custom resource no borra la configuración de la cuenta. Ninguno de los recursos retenidos tiene
        nombre fijo, para que un nuevo despliegue después de `cdk destroy` no choque con ellos.
        """
        log_group = logs.LogGroup(
            self,
            "ModelInvocationLogGroup",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.RETAIN,
        )

        bucket = s3.Bucket(
            self,
            "ModelInvocationLogsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            server_access_logs_bucket=self.access_logs_bucket,
            server_access_logs_prefix="model-invocation-logs/",
            removal_policy=RemovalPolicy.RETAIN,
        )
        bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AmazonBedrockLogsWrite",
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                actions=["s3:PutObject"],
                resources=[
                    bucket.arn_for_objects(
                        f"{INVOCATION_LOGS_PREFIX}/AWSLogs/{self.account}/BedrockModelInvocationLogs/*"
                    )
                ],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:{self.partition}:bedrock:{self.region}:{self.account}:*"},
                },
            )
        )

        role = iam.Role(
            self,
            "ModelInvocationLoggingRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:{self.partition}:bedrock:{self.region}:{self.account}:*"},
                },
            ),
            description="Permite a Bedrock escribir el registro de invocaciones de modelos en CloudWatch",
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                # `log_group_arn` termina en ":*" y produciría un ARN de stream inválido que Bedrock rechaza.
                resources=[
                    f"arn:{self.partition}:logs:{self.region}:{self.account}:log-group:"
                    f"{log_group.log_group_name}:log-stream:aws/bedrock/modelinvocations"
                ],
            )
        )
        role.apply_removal_policy(RemovalPolicy.RETAIN)

        logging_config = {
            "loggingConfig": {
                "cloudWatchConfig": {"logGroupName": log_group.log_group_name, "roleArn": role.role_arn},
                "s3Config": {"bucketName": bucket.bucket_name, "keyPrefix": INVOCATION_LOGS_PREFIX},
                "textDataDeliveryEnabled": True,
                "imageDataDeliveryEnabled": False,
                "embeddingDataDeliveryEnabled": False,
                "videoDataDeliveryEnabled": False,
            }
        }
        put_logging = cr.AwsSdkCall(
            service="bedrock",
            action="PutModelInvocationLoggingConfiguration",
            parameters=logging_config,
            physical_resource_id=cr.PhysicalResourceId.of(f"{config.project_name}-model-invocation-logging"),
        )
        # No existe un recurso de CloudFormation para esta configuración de cuenta y región. Sin on_delete:
        # el registro sigue activo si se elimina el stack.
        invocation_logging = cr.AwsCustomResource(
            self,
            "ModelInvocationLogging",
            on_create=put_logging,
            on_update=put_logging,
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [
                    # Acción a nivel de cuenta: la API no admite permisos por recurso.
                    iam.PolicyStatement(
                        actions=["bedrock:PutModelInvocationLoggingConfiguration"],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(actions=["iam:PassRole"], resources=[role.role_arn]),
                ]
            ),
            log_group=logs.LogGroup(
                self,
                "ModelInvocationLoggingProviderLogs",
                retention=retention(config.log_retention_days),
                removal_policy=RemovalPolicy.DESTROY,
            ),
            install_latest_aws_sdk=False,
        )
        invocation_logging.node.add_dependency(role)
        invocation_logging.node.add_dependency(bucket.policy)
        acknowledge(
            invocation_logging,
            "AwsSolutions-IAM5[Resource::*]",
            "PutModelInvocationLoggingConfiguration es una acción de cuenta y no acepta ARNs de recurso.",
        )
