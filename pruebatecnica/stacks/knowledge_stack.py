"""Ingesta documental y base de conocimiento administrada de Bedrock (pasos 5-7, 14 y 22)."""

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import ASSETS_DIR, backend_code
from pruebatecnica.constructs.nag import acknowledge, acknowledge_wildcards
from pruebatecnica.constructs.python_function import PythonFunction
from pruebatecnica.constructs.runtime_parameter import RuntimeParameter

SAMPLE_DOCS_PREFIX = "ejemplos/"
UPLOADS_PREFIX = "documentos/"


def documents_bucket_name(config: AppConfig, stack: Stack) -> str:
    """Nombre determinista: otros stacks construyen sus políticas sin referencias entre stacks."""
    return f"{config.project_name}-docs-{stack.account}-{stack.region}"


class KnowledgeStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        site_url: str,
        access_logs_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Única fuente de datos de la base de conocimiento (ADR-011).
        self.documents_bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            bucket_name=documents_bucket_name(config, self),
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=False,
            event_bridge_enabled=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="documents-bucket/",
            # La carga con URL prefirmada sale del navegador (ADR-009).
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.PUT],
                    allowed_origins=[site_url, "http://localhost:5173"],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.knowledge_base = self._knowledge_base(config)
        self.data_source = bedrock.CfnDataSource(
            self,
            "DocumentsDataSource",
            name=f"{config.project_name}-documentos",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_deletion_policy="DELETE",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.documents_bucket.bucket_arn,
                ),
            ),
        )

        self.knowledge_base_id_param = RuntimeParameter(
            self,
            "KnowledgeBaseIdParam",
            config=config,
            name="knowledge/knowledge-base-id",
            value=self.knowledge_base.attr_knowledge_base_id,
            description="ID de la base de conocimiento administrada",
        )
        self.data_source_id_param = RuntimeParameter(
            self,
            "DataSourceIdParam",
            config=config,
            name="knowledge/data-source-id",
            value=self.data_source.attr_data_source_id,
            description="ID de la fuente de datos S3 de la base de conocimiento",
        )
        self.documents_bucket_param = RuntimeParameter(
            self,
            "DocumentsBucketParam",
            config=config,
            name="knowledge/documents-bucket",
            value=self.documents_bucket.bucket_name,
            description="Bucket de documentos de la base de conocimiento",
        )

        sync_rule = self._sync_on_upload(config)

        # ADR-025: documentos de ejemplo con BucketDeployment. prune=False para no borrar
        # los documentos que los usuarios suben al mismo bucket.
        sample_docs = s3deploy.BucketDeployment(
            self,
            "SampleDocuments",
            sources=[s3deploy.Source.asset(str(ASSETS_DIR / "knowledge-base"))],
            destination_bucket=self.documents_bucket,
            destination_key_prefix=SAMPLE_DOCS_PREFIX,
            prune=False,
            memory_limit=256,
        )
        # La regla debe existir antes de copiar los documentos para que su carga dispare la sincronización.
        sample_docs.node.add_dependency(sync_rule)
        sample_docs.node.add_dependency(self.data_source)

        CfnOutput(self, "KnowledgeBaseId", value=self.knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "DocumentsBucketName", value=self.documents_bucket.bucket_name)

    def _knowledge_base(self, config: AppConfig) -> bedrock.CfnKnowledgeBase:
        role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal(
                "bedrock.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {
                        "aws:SourceArn": f"arn:{self.partition}:bedrock:{self.region}:{self.account}:knowledge-base/*"
                    },
                },
            ),
            description="Rol de servicio de la base de conocimiento administrada",
        )
        role.add_to_policy(
            iam.PolicyStatement(
                sid="S3ListBucketStatement",
                actions=["s3:ListBucket"],
                resources=[self.documents_bucket.bucket_arn],
                conditions={"StringEquals": {"aws:ResourceAccount": self.account}},
            )
        )
        # ADR-028: el comodín sobre los objetos del bucket es la excepción aceptada.
        role.add_to_policy(
            iam.PolicyStatement(
                sid="S3GetObjectStatement",
                actions=["s3:GetObject"],
                resources=[self.documents_bucket.arn_for_objects("*")],
                conditions={"StringEquals": {"aws:ResourceAccount": self.account}},
            )
        )

        knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=f"{config.project_name}-conocimiento",
            description="Documentación interna consultada por el agente conversacional",
            role_arn=role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="MANAGED",
                managed_knowledge_base_configuration=bedrock.CfnKnowledgeBase.ManagedKnowledgeBaseConfigurationProperty(
                    embedding_model_type="MANAGED",
                ),
            ),
        )
        knowledge_base.node.add_dependency(role)
        acknowledge_wildcards(
            role, "ADR-028: la base de conocimiento lee cualquier objeto del bucket de documentos, su única fuente."
        )
        return knowledge_base

    def _sync_on_upload(self, config: AppConfig) -> events.Rule:
        """ADR-010: cada carga o borrado lanza una sincronización incremental."""
        # Recibe los eventos que no se pudieron entregar o procesar, para revisarlos a mano.
        dead_letters = sqs.Queue(
            self,
            "SyncDeadLetterQueue",
            enforce_ssl=True,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            retention_period=Duration.days(14),
        )
        for rule in ("AwsSolutions-SQS3", "Serverless-SQSRedrivePolicy"):
            acknowledge(dead_letters, rule, "Esta cola es la DLQ de la sincronización; no necesita otra DLQ.")
        sync = PythonFunction(
            self,
            "SyncOnUpload",
            code=backend_code(),
            handler="triggers.kb_sync_on_upload.handler",
            service_name="kb-sync-on-upload",
            description="Sincroniza la base de conocimiento cuando cambia el bucket de documentos",
            log_retention_days=config.log_retention_days,
            environment={
                "KNOWLEDGE_BASE_ID_PARAM": self.knowledge_base_id_param.parameter_name,
                "DATA_SOURCE_ID_PARAM": self.data_source_id_param.parameter_name,
            },
            timeout=Duration.seconds(30),
            memory_size=256,
            dead_letter_queue=dead_letters,
        )
        self.grant_sync(sync.function)
        self.knowledge_base_id_param.grant_read(sync.function)
        self.data_source_id_param.grant_read(sync.function)

        return events.Rule(
            self,
            "DocumentsChangedRule",
            description="Cambios en el bucket de documentos de la base de conocimiento",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created", "Object Deleted"],
                detail={"bucket": {"name": [self.documents_bucket.bucket_name]}},
            ),
            targets=[targets.LambdaFunction(sync.function, dead_letter_queue=dead_letters, retry_attempts=2)],
        )

    def grant_sync(self, grantee: iam.IGrantable) -> None:
        """Permisos para lanzar y consultar sincronizaciones de la base de conocimiento."""
        iam.Grant.add_to_principal(
            grantee=grantee,
            actions=["bedrock:StartIngestionJob", "bedrock:ListIngestionJobs"],
            resource_arns=[self.knowledge_base.attr_knowledge_base_arn],
        )
