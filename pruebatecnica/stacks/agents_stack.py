"""Agentes: swarm en AgentCore Runtime, gateway MCP, herramientas y guardrails (pasos 10-16)."""

import json

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import custom_resources as cr
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import AGENTS_DIR, ASSETS_DIR, BACKEND_DIR, backend_code
from pruebatecnica.constructs.bedrock_models import model_invoke_statements
from pruebatecnica.constructs.nag import acknowledge_wildcards
from pruebatecnica.constructs.python_function import PythonFunction, retention
from pruebatecnica.constructs.runtime_parameter import RuntimeParameter

# ADR-026: mensaje que ve el usuario cuando el guardrail bloquea la solicitud.
BLOCKED_MESSAGE = "Esta respuesta fue bloqueada por los guardrails."

# Nombres de los destinos del gateway. El gateway publica cada herramienta como
# "<destino>___<herramienta>", y los agentes filtran sus herramientas por ese prefijo.
KNOWLEDGE_TARGET = "conocimiento"
WEB_SEARCH_TARGET = "busqueda-web"
REQUESTS_TARGET_PREFIX = "solicitudes"

_SCHEMA_TYPES = {
    "object": agentcore.SchemaDefinitionType.OBJECT,
    "string": agentcore.SchemaDefinitionType.STRING,
    "integer": agentcore.SchemaDefinitionType.INTEGER,
    "number": agentcore.SchemaDefinitionType.NUMBER,
    "boolean": agentcore.SchemaDefinitionType.BOOLEAN,
    "array": agentcore.SchemaDefinitionType.ARRAY,
}

# Acciones de DynamoDB por herramienta: ninguna puede borrar (ADR-021).
_TOOL_ACTIONS = {
    "create_request": ["dynamodb:PutItem"],
    "get_request": ["dynamodb:GetItem"],
    "list_requests": ["dynamodb:Scan"],
    "update_request_summary": ["dynamodb:GetItem", "dynamodb:UpdateItem"],
    "update_request_priority": ["dynamodb:UpdateItem"],
    "update_request_effort": ["dynamodb:UpdateItem"],
    "update_request_status": ["dynamodb:UpdateItem"],
}


def _schema(definition: dict) -> agentcore.SchemaDefinition:
    """Convierte un JSON Schema simple al tipo SchemaDefinition del gateway."""
    return agentcore.SchemaDefinition(
        type=_SCHEMA_TYPES[definition["type"]],
        description=definition.get("description"),
        properties={name: _schema(prop) for name, prop in definition.get("properties", {}).items()} or None,
        items=_schema(definition["items"]) if "items" in definition else None,
        required=definition.get("required"),
    )


def _to_dynamodb_item(item: dict) -> dict:
    return {key: {"S": value} for key, value in item.items()}


class AgentsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: AppConfig,
        knowledge_base: bedrock.CfnKnowledgeBase,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._config = config

        guardrail, guardrail_version = self._guardrail()
        self.requests_table = self._requests_table()
        self.gateway = self._gateway(knowledge_base)

        self.model_id_param = RuntimeParameter(
            self,
            "AgentModelIdParam",
            config=config,
            name="agents/model-id",
            value=config.agent_model_id,
            description="Modelo de Bedrock de los agentes (ADR-016)",
        )
        params = {
            "MODEL_ID_PARAM": self.model_id_param,
            "GUARDRAIL_ID_PARAM": RuntimeParameter(
                self,
                "GuardrailIdParam",
                config=config,
                name="agents/guardrail-id",
                value=guardrail.attr_guardrail_id,
                description="ID del guardrail de prompt injection",
            ),
            "GUARDRAIL_VERSION_PARAM": RuntimeParameter(
                self,
                "GuardrailVersionParam",
                config=config,
                name="agents/guardrail-version",
                value=guardrail_version.attr_version,
                description="Versión publicada del guardrail",
            ),
            "GATEWAY_URL_PARAM": RuntimeParameter(
                self,
                "GatewayUrlParam",
                config=config,
                name="agents/gateway-url",
                value=self.gateway.gateway_url or "",
                description="URL MCP del gateway de herramientas",
            ),
            "BLOCKED_MESSAGE_PARAM": RuntimeParameter(
                self,
                "BlockedMessageParam",
                config=config,
                name="agents/blocked-message",
                value=BLOCKED_MESSAGE,
                description="Mensaje que recibe el usuario cuando el guardrail interviene",
            ),
        }
        # Los mismos parámetros los usa la tarea de evaluación, que ejecuta el mismo swarm.
        self.agent_parameters = params
        self.agent_environment = {name: param.parameter_name for name, param in params.items()}
        self.agent_environment.update(
            {
                "KNOWLEDGE_TARGET": KNOWLEDGE_TARGET,
                "WEB_SEARCH_TARGET": WEB_SEARCH_TARGET,
                "REQUESTS_TARGET_PREFIX": REQUESTS_TARGET_PREFIX,
            }
        )
        self.guardrail_arn = guardrail.attr_guardrail_arn

        # Contexto corto de cada conversación, por sessionId de AgentCore Runtime (solo memoria de corto plazo).
        self.memory = agentcore.Memory(
            self,
            "ConversationMemory",
            memory_name=f"{config.project_name.replace('-', '_')}_conversaciones",
            description="Historial reciente de cada sesion del swarm",
            # Solo hace falta el contexto de la conversación en curso; 7 días es el mínimo que admite el servicio.
            expiration_duration=Duration.days(7),
        )
        self.memory_id_param = RuntimeParameter(
            self,
            "MemoryIdParam",
            config=config,
            name="agents/memory-id",
            value=self.memory.memory_id,
            description="Memoria de AgentCore con el contexto corto de cada conversación",
        )

        self.runtime = self._runtime()
        self.grant_agent_permissions(self.runtime)
        self.memory.grant_read_short_term_memory(self.runtime)
        self.memory.grant_write(self.runtime)
        self.memory_id_param.grant_read(self.runtime)
        acknowledge_wildcards(
            self.runtime,
            "El rol que crea el construct Runtime usa comodines para sus log groups, la identidad de carga de trabajo "
            "y X-Ray; el perfil de inferencia entre regiones exige el ARN del modelo base con región comodín "
            "(ADR-028).",
        )
        acknowledge_wildcards(
            self.gateway,
            "El construct Gateway da permiso de invocar cada Lambda de herramienta con cualquier versión o alias (:*).",
        )

        self.runtime_arn_param = RuntimeParameter(
            self,
            "RuntimeArnParam",
            config=config,
            name="agents/runtime-arn",
            value=self.runtime.agent_runtime_arn,
            description="ARN del runtime de AgentCore con el swarm de agentes",
        )

        CfnOutput(self, "GatewayUrl", value=self.gateway.gateway_url or "")
        CfnOutput(self, "AgentRuntimeArn", value=self.runtime.agent_runtime_arn)

    # --- Guardrails (paso 12, ADR-026) -------------------------------------------------------

    def _guardrail(self) -> tuple[bedrock.CfnGuardrail, bedrock.CfnGuardrailVersion]:
        guardrail = bedrock.CfnGuardrail(
            self,
            "PromptAttackGuardrail",
            name=f"{self._config.project_name}-prompt-injection",
            description="Solo detecta y bloquea ataques de prompt injection",
            blocked_input_messaging=BLOCKED_MESSAGE,
            blocked_outputs_messaging=BLOCKED_MESSAGE,
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    # Los ataques de prompt solo se evalúan en la entrada; la salida debe ser NONE. Con HIGH o MEDIUM,
                    # el contexto de coordinación que el swarm agrega al mensaje se bloquea (ADR-026).
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="PROMPT_ATTACK", input_strength="LOW", output_strength="NONE"
                    )
                ]
            ),
        )
        version = bedrock.CfnGuardrailVersion(
            self,
            "PromptAttackGuardrailVersion",
            guardrail_identifier=guardrail.attr_guardrail_id,
            # Cambiar la descripción reemplaza la versión; así un cambio en el guardrail publica una nueva.
            description="Versión publicada para los agentes (ataques de prompt con intensidad LOW)",
        )
        return guardrail, version

    # --- Solicitudes (paso 16, ADR-020 a ADR-022 y ADR-042) ----------------------------------

    def _requests_table(self) -> dynamodb.TableV2:
        table = dynamodb.TableV2(
            self,
            "RequestsTable",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ADR-025: las 10 solicitudes de ejemplo se precargan desde un JSON versionado.
        sample_requests = json.loads((ASSETS_DIR / "solicitudes" / "solicitudes.json").read_text(encoding="utf-8"))
        batch_write = {
            "RequestItems": {
                table.table_name: [{"PutRequest": {"Item": _to_dynamodb_item(item)}} for item in sample_requests]
            }
        }
        seed = cr.AwsCustomResource(
            self,
            "SeedSampleRequests",
            on_create=cr.AwsSdkCall(
                service="DynamoDB",
                action="BatchWriteItem",
                parameters=batch_write,
                physical_resource_id=cr.PhysicalResourceId.of("sample-requests-v1"),
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements(
                [iam.PolicyStatement(actions=["dynamodb:BatchWriteItem"], resources=[table.table_arn])]
            ),
            log_group=logs.LogGroup(
                self,
                "SeedSampleRequestsLogs",
                retention=retention(self._config.log_retention_days),
                removal_policy=RemovalPolicy.DESTROY,
            ),
            install_latest_aws_sdk=False,
        )
        seed.node.add_dependency(table)
        return table

    def _request_tools(self, gateway: agentcore.Gateway) -> None:
        schemas = json.loads((BACKEND_DIR / "tools" / "tool_schemas.json").read_text(encoding="utf-8"))
        code = backend_code()
        for tool_name, schema in schemas.items():
            construct_name = "".join(part.capitalize() for part in tool_name.split("_"))
            tool = PythonFunction(
                self,
                f"{construct_name}Tool",
                code=code,
                handler=f"tools.{tool_name}.handler",
                service_name=f"tool-{tool_name.replace('_', '-')}",
                description=schema["description"][:256],
                log_retention_days=self._config.log_retention_days,
                environment={"REQUESTS_TABLE_NAME": self.requests_table.table_name},
                timeout=Duration.seconds(15),
                memory_size=256,
            )
            tool.role.add_to_policy(
                iam.PolicyStatement(actions=_TOOL_ACTIONS[tool_name], resources=[self.requests_table.table_arn])
            )
            # ADR-020: una Lambda por operación, cada una registrada como destino del gateway.
            gateway.add_lambda_target(
                f"{construct_name}Target",
                gateway_target_name=f"{REQUESTS_TARGET_PREFIX}-{tool_name.replace('_', '-')}",
                description=schema["description"][:200],
                lambda_function=tool.function,
                tool_schema=agentcore.ToolSchema.from_inline(
                    [
                        agentcore.ToolDefinition(
                            name=tool_name,
                            description=schema["description"],
                            input_schema=_schema(schema["inputSchema"]),
                        )
                    ]
                ),
            )

    # --- Gateway MCP (pasos 13-15, ADR-019 y ADR-023) ----------------------------------------

    def _gateway(self, knowledge_base: bedrock.CfnKnowledgeBase) -> agentcore.Gateway:
        gateway = agentcore.Gateway(
            self,
            "ToolsGateway",
            gateway_name=f"{self._config.project_name}-tools",
            description="Herramientas de los agentes: base de conocimiento, busqueda web y solicitudes",
            authorizer_configuration=agentcore.GatewayAuthorizer.using_aws_iam(),
        )

        self._request_tools(gateway)

        # Conector administrado de la base de conocimiento: el agente solo controla el texto de la consulta.
        gateway.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock:GetKnowledgeBase", "bedrock:Retrieve"],
                resources=[knowledge_base.attr_knowledge_base_arn],
            )
        )
        knowledge_target = agentcore.CfnGatewayTarget(
            self,
            "KnowledgeBaseTarget",
            gateway_identifier=gateway.gateway_id,
            name=KNOWLEDGE_TARGET,
            description="Recupera fragmentos y fuentes de la base de conocimiento interna",
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    connector=agentcore.CfnGatewayTarget.ConnectorTargetConfigurationProperty(
                        source=agentcore.CfnGatewayTarget.ConnectorSourceProperty(
                            connector_id="bedrock-knowledge-bases"
                        ),
                        configurations=[
                            agentcore.CfnGatewayTarget.ConnectorConfigurationProperty(
                                name="Retrieve",
                                description=(
                                    "Busca en la base de conocimiento interna de la empresa. Devuelve fragmentos "
                                    "de documentos con su ubicación, que se deben citar como fuente."
                                ),
                                parameter_values={
                                    "knowledgeBaseId": knowledge_base.attr_knowledge_base_id,
                                    "retrievalConfiguration": {"managedSearchConfiguration": {"numberOfResults": 10}},
                                },
                                parameter_overrides=[
                                    agentcore.CfnGatewayTarget.ConnectorParameterOverrideProperty(
                                        path="$.retrievalQuery.text",
                                        description="Consulta de búsqueda con palabras clave específicas.",
                                        visible=True,
                                    )
                                ],
                            )
                        ],
                    )
                )
            ),
        )
        knowledge_target.node.add_dependency(gateway.role)

        # Búsqueda web solo en la documentación de AWS y Azure (paso 15).
        gateway.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeWebSearch"],
                resources=[f"arn:{self.partition}:bedrock-agentcore:{self.region}:aws:tool/web-search.v1"],
            )
        )
        web_search_target = agentcore.CfnGatewayTarget(
            self,
            "WebSearchTarget",
            gateway_identifier=gateway.gateway_id,
            name=WEB_SEARCH_TARGET,
            description="Busqueda web restringida a la documentacion de AWS y Azure",
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    connector=agentcore.CfnGatewayTarget.ConnectorTargetConfigurationProperty(
                        source=agentcore.CfnGatewayTarget.ConnectorSourceProperty(connector_id="web-search"),
                        configurations=[
                            agentcore.CfnGatewayTarget.ConnectorConfigurationProperty(
                                name="WebSearch",
                                parameter_values={"domainFilter": {"include": self._config.web_search_allowed_domains}},
                            )
                        ],
                    )
                )
            ),
        )
        web_search_target.node.add_dependency(gateway.role)
        return gateway

    # --- Runtime (pasos 10, 11 y 24, ADR-015) ------------------------------------------------

    def _runtime(self) -> agentcore.Runtime:
        log_group = logs.LogGroup(
            self,
            "RuntimeLogGroup",
            # El prefijo /aws/vendedlogs/ permite la entrega de logs sin una política de recursos propia.
            log_group_name=f"/aws/vendedlogs/bedrock-agentcore/{self._config.project_name}-swarm",
            retention=retention(self._config.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )
        artifact = agentcore.AgentRuntimeArtifact.from_asset(
            str(AGENTS_DIR),
            file="Dockerfile.runtime",
            platform=ecr_assets.Platform.LINUX_ARM64,
            exclude=["tests", "**/__pycache__", ".venv", ".pytest_cache", ".ruff_cache"],
        )
        return agentcore.Runtime(
            self,
            "SwarmRuntime",
            runtime_name=f"{self._config.project_name.replace('-', '_')}_swarm",
            description="Swarm de agentes: conversacional, modernizacion y recomendador cloud",
            agent_runtime_artifact=artifact,
            environment_variables={
                **self.agent_environment,
                "MEMORY_ID_PARAM": self.memory_id_param.parameter_name,
                "AGENT_OBSERVABILITY_ENABLED": "true",
                "OTEL_PYTHON_DISTRO": "aws_distro",
                "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
            },
            logging_configs=[
                agentcore.LoggingConfig(
                    log_type=agentcore.LogType.APPLICATION_LOGS,
                    destination=agentcore.LoggingDestination.cloud_watch_logs(log_group),
                )
            ],
            manage_delivery_resource_policy=False,
            # La entrega de trazas a X-Ray exige CloudWatch Transaction Search, que no se activa en el despliegue.
            tracing_enabled=False,
        )

    def grant_agent_permissions(self, grantee: iam.IGrantable) -> None:
        """Permisos que necesita cualquier proceso que ejecute el swarm (runtime o evaluación)."""
        for statement in model_invoke_statements(
            self, self._config.agent_model_id, ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        ):
            grantee.grant_principal.add_to_principal_policy(statement)
        iam.Grant.add_to_principal(
            grantee=grantee, actions=["bedrock:ApplyGuardrail"], resource_arns=[self.guardrail_arn]
        )
        iam.Grant.add_to_principal(
            grantee=grantee, actions=["bedrock-agentcore:InvokeGateway"], resource_arns=[self.gateway.gateway_arn]
        )
        for param in self.agent_parameters.values():
            param.grant_read(grantee)
