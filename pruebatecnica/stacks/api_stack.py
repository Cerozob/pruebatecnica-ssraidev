"""API REST de API Gateway con una Lambda de Powertools por endpoint (pasos 3, 4, 8, 9, 19 y 26)."""

import json
from dataclasses import dataclass, field

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import backend_code
from pruebatecnica.constructs.nag import acknowledge, acknowledge_wildcards
from pruebatecnica.constructs.python_function import PythonFunction, retention
from pruebatecnica.constructs.runtime_parameter import RuntimeParameter
from pruebatecnica.stacks.agents_stack import AgentsStack
from pruebatecnica.stacks.evaluation_stack import EvaluationStack
from pruebatecnica.stacks.knowledge_stack import UPLOADS_PREFIX, KnowledgeStack, documents_bucket_name

LOCAL_DEV_ORIGIN = "http://localhost:5173"


@dataclass
class Endpoint:
    construct_id: str
    method: str
    path: str
    handler: str
    description: str
    timeout: Duration = field(default_factory=lambda: Duration.seconds(30))
    memory_size: int = 512


class ApiStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        site_url: str,
        user_pool: cognito.IUserPool,
        knowledge: KnowledgeStack,
        agents: AgentsStack,
        evaluation: EvaluationStack,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._config = config
        self._code = backend_code()
        self._site_url = site_url

        # Paso 8 y ADR-017: historial de conversaciones.
        self.conversations_table = dynamodb.TableV2(
            self,
            "ConversationsTable",
            partition_key=dynamodb.Attribute(name="conversationId", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            global_secondary_indexes=[
                dynamodb.GlobalSecondaryIndexPropsV2(
                    # Conversaciones de cada usuario, la más reciente primero.
                    index_name="byUser",
                    partition_key=dynamodb.Attribute(name="userId", type=dynamodb.AttributeType.STRING),
                    sort_key=dynamodb.Attribute(name="updatedAt", type=dynamodb.AttributeType.STRING),
                )
            ],
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.log_tag_filters_param = RuntimeParameter(
            self,
            "LogTagFiltersParam",
            config=config,
            name="logs/tag-filters",
            value=json.dumps(config.tags),
            description="Etiquetas que debe tener un log group para mostrarse en el visor (ADR-037)",
        )

        self.api = self._rest_api(user_pool)

        chat_endpoints = [
            Endpoint(
                "CreateConversation",
                "POST",
                "/conversations",
                "api.create_conversation.handler",
                "Crea una conversacion con su primer mensaje y la sesion del runtime",
                # Sigue guardando la respuesta aunque API Gateway corte la conexión a los 29 s.
                timeout=Duration.minutes(5),
            ),
            Endpoint(
                "SendMessage",
                "POST",
                "/conversations/{conversationId}/messages",
                "api.send_message.handler",
                "Envia un mensaje a la sesion del swarm y guarda el turno",
                timeout=Duration.minutes(5),
            ),
        ]
        for endpoint in chat_endpoints:
            function = self._endpoint(endpoint)
            self._grant_conversations(function, write=True)
            # Sin comodines: el runtime y su endpoint por defecto.
            function.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["bedrock-agentcore:InvokeAgentRuntime"],
                    resources=[
                        agents.runtime.agent_runtime_arn,
                        f"{agents.runtime.agent_runtime_arn}/runtime-endpoint/DEFAULT",
                    ],
                )
            )
            agents.runtime_arn_param.grant_read(function)
            function.add_environment("RUNTIME_ARN_PARAM", agents.runtime_arn_param.parameter_name)

        list_conversations = self._endpoint(
            Endpoint(
                "ListConversations",
                "GET",
                "/conversations",
                "api.list_conversations.handler",
                "Lista las conversaciones",
            )
        )
        self._grant_conversations(list_conversations)

        get_conversation = self._endpoint(
            Endpoint(
                "GetConversation",
                "GET",
                "/conversations/{conversationId}",
                "api.get_conversation.handler",
                "Devuelve el historial de una conversacion",
            )
        )
        self._grant_conversations(get_conversation)

        upload_url = self._endpoint(
            Endpoint(
                "CreateUploadUrl",
                "POST",
                "/documents/upload-url",
                "api.create_upload_url.handler",
                "Genera una URL prefirmada para subir un documento a S3",
            )
        )
        upload_url.add_to_role_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[f"arn:{self.partition}:s3:::{documents_bucket_name(config, self)}/{UPLOADS_PREFIX}*"],
            )
        )
        acknowledge_wildcards(
            upload_url.node.scope,
            "Cada carga usa una clave nueva bajo el prefijo de documentos; el permiso se limita a ese prefijo.",
        )
        knowledge.documents_bucket_param.grant_read(upload_url)
        upload_url.add_environment("DOCUMENTS_BUCKET_PARAM", knowledge.documents_bucket_param.parameter_name)

        sync = self._endpoint(
            Endpoint(
                "SyncKnowledgeBase",
                "POST",
                "/knowledge-base/sync",
                "api.sync_knowledge_base.handler",
                "Lanza una sincronizacion manual de la base de conocimiento",
            )
        )
        knowledge.grant_sync(sync)
        knowledge.knowledge_base_id_param.grant_read(sync)
        knowledge.data_source_id_param.grant_read(sync)
        sync.add_environment("KNOWLEDGE_BASE_ID_PARAM", knowledge.knowledge_base_id_param.parameter_name)
        sync.add_environment("DATA_SOURCE_ID_PARAM", knowledge.data_source_id_param.parameter_name)

        self._log_endpoints()
        self._evaluation_endpoints(evaluation)

        CfnOutput(self, "ApiUrl", value=self.api.url)

    def _grant_conversations(self, function, write: bool = False) -> None:
        """Permisos explícitos sobre la tabla y su único índice, sin el comodín index/* de grant_read_data."""
        actions = ["dynamodb:GetItem", "dynamodb:Query"]
        if write:
            actions += ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        function.add_to_role_policy(
            iam.PolicyStatement(
                actions=actions,
                resources=[
                    self.conversations_table.table_arn,
                    f"{self.conversations_table.table_arn}/index/byUser",
                ],
            )
        )

    def _rest_api(self, user_pool: cognito.IUserPool) -> apigw.RestApi:
        access_logs = logs.LogGroup(
            self,
            "ApiAccessLogs",
            retention=retention(self._config.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )
        api = apigw.RestApi(
            self,
            "RestApi",
            rest_api_name=f"{self._config.project_name}-api",
            description="API del asistente RAG agentico",
            endpoint_types=[apigw.EndpointType.REGIONAL],
            # Necesario para que API Gateway pueda escribir los logs de acceso en CloudWatch.
            cloud_watch_role=True,
            cloud_watch_role_removal_policy=RemovalPolicy.DESTROY,
            deploy_options=apigw.StageOptions(
                stage_name="api",
                access_log_destination=apigw.LogGroupLogDestination(access_logs),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
                logging_level=apigw.MethodLoggingLevel.ERROR,
                metrics_enabled=True,
                # ADR-008: limitación de tasa para proteger el backend y el consumo de modelos.
                throttling_rate_limit=self._config.api_throttle_rate_limit,
                throttling_burst_limit=self._config.api_throttle_burst_limit,
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=[self._site_url, LOCAL_DEV_ORIGIN],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Authorization", "Content-Type"],
            ),
        )
        # Los errores de API Gateway (401, 429, 504) también deben llevar CORS para que el navegador los lea.
        cors_headers = {"Access-Control-Allow-Origin": "'*'", "Access-Control-Allow-Headers": "'*'"}
        api.add_gateway_response("Default4xx", type=apigw.ResponseType.DEFAULT_4_XX, response_headers=cors_headers)
        api.add_gateway_response("Default5xx", type=apigw.ResponseType.DEFAULT_5_XX, response_headers=cors_headers)

        self._authorizer = apigw.CognitoUserPoolsAuthorizer(self, "CognitoAuthorizer", cognito_user_pools=[user_pool])
        self._validator = api.add_request_validator(
            "RequestValidator", validate_request_body=True, validate_request_parameters=True
        )

        acknowledge(api, "AwsSolutions-APIG3", "AWS WAF queda fuera por costo (ADR-039).")
        acknowledge(
            api,
            "AwsSolutions-IAM4[Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs]",
            "El rol de cuenta de API Gateway para CloudWatch usa la política administrada que exige el servicio.",
        )
        acknowledge(api, "Serverless-APIGWXrayEnabled", "X-Ray queda como mejora futura de observabilidad (ADR-039).")
        return api

    def _endpoint(self, endpoint: Endpoint):
        function = PythonFunction(
            self,
            endpoint.construct_id,
            code=self._code,
            handler=endpoint.handler,
            service_name=endpoint.construct_id,
            description=endpoint.description,
            log_retention_days=self._config.log_retention_days,
            environment={
                "ALLOWED_ORIGINS": f"{self._site_url},{LOCAL_DEV_ORIGIN}",
                "CONVERSATIONS_TABLE_NAME": self.conversations_table.table_name,
            },
            timeout=endpoint.timeout,
            memory_size=endpoint.memory_size,
        ).function

        resource = self.api.root.resource_for_path(endpoint.path)
        resource.add_method(
            endpoint.method,
            apigw.LambdaIntegration(function, timeout=Duration.seconds(29)),
            authorizer=self._authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            request_validator=self._validator,
        )
        return function

    def _log_endpoints(self) -> None:
        list_groups = self._endpoint(
            Endpoint(
                "ListLogGroups",
                "GET",
                "/logs/groups",
                "api.list_log_groups.handler",
                "Lista los log groups con las etiquetas de la aplicacion",
            )
        )
        get_events = self._endpoint(
            Endpoint(
                "GetLogEvents",
                "GET",
                "/logs/groups/{logGroupId}/events",
                "api.get_log_events.handler",
                "Devuelve los eventos de un log group como texto plano",
            )
        )
        for function in (list_groups, get_events):
            self.log_tag_filters_param.grant_read(function)
            function.add_environment("LOG_TAG_FILTERS_PARAM", self.log_tag_filters_param.parameter_name)

        # Listar log groups no admite permisos por recurso.
        list_groups.add_to_role_policy(
            iam.PolicyStatement(actions=["logs:ListLogGroups", "logs:DescribeLogGroups"], resources=["*"])
        )
        list_groups.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:ListTagsForResource"],
                resources=[f"arn:{self.partition}:logs:{self.region}:{self.account}:log-group:*"],
            )
        )
        get_events.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:ListTagsForResource"],
                resources=[f"arn:{self.partition}:logs:{self.region}:{self.account}:log-group:*"],
            )
        )
        # Solo se pueden leer los log groups que llevan las etiquetas de la aplicación.
        get_events.add_to_role_policy(
            iam.PolicyStatement(
                actions=["logs:FilterLogEvents"],
                resources=[f"arn:{self.partition}:logs:{self.region}:{self.account}:log-group:*"],
                conditions={
                    "StringEquals": {f"aws:ResourceTag/{key}": value for key, value in self._config.tags.items()}
                },
            )
        )
        for function in (list_groups, get_events):
            acknowledge_wildcards(
                function.node.scope,
                "El visor de logs descubre los log groups por etiqueta, y listar log groups no admite permisos por "
                "recurso; la lectura de eventos está condicionada a las etiquetas de la aplicación (ADR-037).",
            )

    def _evaluation_endpoints(self, evaluation: EvaluationStack) -> None:
        environment = {"EVALUATIONS_TABLE_NAME": evaluation.evaluations_table.table_name}

        start = self._endpoint(
            Endpoint(
                "StartEvaluation",
                "POST",
                "/evaluations",
                "api.start_evaluation.handler",
                "Inicia una evaluacion agentica",
            )
        )
        start.add_to_role_policy(
            iam.PolicyStatement(actions=["dynamodb:PutItem"], resources=[evaluation.evaluations_table.table_arn])
        )
        evaluation.state_machine.grant_start_execution(start)
        start.add_environment("EVALUATION_STATE_MACHINE_ARN", evaluation.state_machine.state_machine_arn)

        list_evaluations = self._endpoint(
            Endpoint("ListEvaluations", "GET", "/evaluations", "api.list_evaluations.handler", "Lista las evaluaciones")
        )
        get_evaluation = self._endpoint(
            Endpoint(
                "GetEvaluation",
                "GET",
                "/evaluations/{evaluationId}",
                "api.get_evaluation.handler",
                "Devuelve el progreso y los resultados de una evaluacion",
            )
        )
        for function in (start, list_evaluations, get_evaluation):
            for key, value in environment.items():
                function.add_environment(key, value)
        evaluation.evaluations_table.grant_read_data(list_evaluations)
        evaluation.evaluations_table.grant_read_data(get_evaluation)
