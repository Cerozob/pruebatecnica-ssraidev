"""Evaluación agéntica (pasos 17-19).

Step Functions lanza una tarea de Fargate con Strands Evals y AgentCore Evaluations.
"""

from aws_cdk import CfnOutput, Duration, Fn, RemovalPolicy, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct

from pruebatecnica.config import AppConfig
from pruebatecnica.constructs.assets import AGENTS_DIR
from pruebatecnica.constructs.bedrock_models import model_invoke_statements
from pruebatecnica.constructs.nag import acknowledge, acknowledge_wildcards
from pruebatecnica.constructs.python_function import retention
from pruebatecnica.constructs.runtime_parameter import RuntimeParameter
from pruebatecnica.stacks.agents_stack import AgentsStack

GROUNDEDNESS_PROMPT = AGENTS_DIR / "evaluation" / "prompts" / "groundedness_evaluator.md"


class EvaluationStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, *, config: AppConfig, agents: AgentsStack, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._config = config

        self.evaluations_table = dynamodb.TableV2(
            self,
            "EvaluationsTable",
            partition_key=dynamodb.Attribute(name="evaluationId", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ADR-030 y ADR-032: evaluador de groundedness de AgentCore con el modelo juez configurado.
        self.groundedness_evaluator = agentcore.Evaluator(
            self,
            "GroundednessEvaluator",
            evaluator_name=f"{config.project_name.replace('-', '_')}_groundedness",
            description="Verifica que la respuesta se base en sus fuentes y las cite",
            level=agentcore.EvaluationLevel.TRACE,
            evaluator_config=agentcore.EvaluatorConfig.llm_as_a_judge(
                instructions=GROUNDEDNESS_PROMPT.read_text(encoding="utf-8"),
                model_id=config.judge_model_id,
                rating_scale=agentcore.EvaluatorRatingScale.numerical(
                    [
                        agentcore.NumericalRatingOption(
                            label="No fundamentada",
                            definition=(
                                "La respuesta afirma hechos que no están en las fuentes o no cita ninguna fuente."
                            ),
                            value=0,
                        ),
                        agentcore.NumericalRatingOption(
                            label="Parcialmente fundamentada",
                            definition=(
                                "La mayor parte está respaldada por las fuentes, pero alguna afirmación no, "
                                "o faltan citas."
                            ),
                            value=0.5,
                        ),
                        agentcore.NumericalRatingOption(
                            label="Fundamentada",
                            definition=(
                                "Toda afirmación está respaldada por las fuentes recuperadas y la respuesta las cita."
                            ),
                            value=1,
                        ),
                    ]
                ),
            ),
        )

        self.judge_model_id_param = RuntimeParameter(
            self,
            "JudgeModelIdParam",
            config=config,
            name="evaluation/judge-model-id",
            value=config.judge_model_id,
            description="Modelo juez de las evaluaciones (ADR-032)",
        )
        self.groundedness_evaluator_param = RuntimeParameter(
            self,
            "GroundednessEvaluatorParam",
            config=config,
            # El SDK espera el id: con el ARN, AgentCore autoriza contra "evaluator/<arn>" y la política no coincide.
            name="evaluation/groundedness-evaluator-id",
            value=self.groundedness_evaluator.evaluator_id,
            description="Evaluador de groundedness de AgentCore Evaluations",
        )

        task_definition, container = self._task_definition(agents)
        self.state_machine = self._state_machine(task_definition, container)

        CfnOutput(self, "EvaluationStateMachineArn", value=self.state_machine.state_machine_arn)

    @property
    def availability_zones(self) -> list[str]:
        # Las dos primeras zonas de la región, resueltas por CloudFormation (Fn::GetAZs): cdk synth no
        # necesita credenciales para consultarlas y no se fijan nombres de zona.
        return [Fn.select(0, Fn.get_azs()), Fn.select(1, Fn.get_azs())]

    def _task_definition(self, agents: AgentsStack) -> tuple[ecs.FargateTaskDefinition, ecs.ContainerDefinition]:
        # ADR-002: Fargate porque una evaluación puede superar los 15 minutos de Lambda.
        # Subredes públicas sin NAT Gateway: la tarea no recibe tráfico entrante y solo llama a APIs de AWS.
        self.vpc = ec2.Vpc(
            self,
            "EvaluationVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC)],
        )
        self.vpc.add_gateway_endpoint("S3Endpoint", service=ec2.GatewayVpcEndpointAwsService.S3)
        self.vpc.add_gateway_endpoint("DynamoDbEndpoint", service=ec2.GatewayVpcEndpointAwsService.DYNAMODB)
        acknowledge(self.vpc, "AwsSolutions-VPC7", "Los flow logs quedan fuera del alcance por costo (ADR-039).")

        self.security_group = ec2.SecurityGroup(
            self,
            "EvaluationTaskSecurityGroup",
            vpc=self.vpc,
            description="Tarea de evaluacion: sin trafico entrante",
            allow_all_outbound=True,
        )

        self.cluster = ecs.Cluster(self, "EvaluationCluster", vpc=self.vpc)
        acknowledge(
            self.cluster,
            "AwsSolutions-ECS4",
            "Container Insights queda fuera por costo; la tarea corre solo durante una evaluación (ADR-039).",
        )

        log_group = logs.LogGroup(
            self,
            "EvaluationTaskLogGroup",
            retention=retention(self._config.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )

        task_definition = ecs.FargateTaskDefinition(
            self,
            "EvaluationTask",
            cpu=1024,
            memory_limit_mib=2048,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )
        container = task_definition.add_container(
            "Evaluator",
            image=ecs.ContainerImage.from_asset(
                str(AGENTS_DIR),
                file="Dockerfile.evaluation",
                platform=ecr_assets.Platform.LINUX_ARM64,
                exclude=["tests", "**/__pycache__", ".venv", ".pytest_cache", ".ruff_cache"],
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="evaluation", log_group=log_group),
            environment={
                **agents.agent_environment,
                "EVALUATIONS_TABLE_NAME": self.evaluations_table.table_name,
                "JUDGE_MODEL_ID_PARAM": self.judge_model_id_param.parameter_name,
                "GROUNDEDNESS_EVALUATOR_ID_PARAM": self.groundedness_evaluator_param.parameter_name,
            },
        )
        acknowledge(
            task_definition,
            "AwsSolutions-ECS2",
            "Las variables de entorno solo contienen nombres de parámetros y de la tabla, no secretos.",
        )

        task_role = task_definition.task_role
        # La evaluación ejecuta el mismo swarm que el runtime, con los mismos permisos.
        agents.grant_agent_permissions(task_role)
        # La tarea solo actualiza su propia evaluación: sin borrado ni escaneo.
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["dynamodb:UpdateItem", "dynamodb:GetItem"], resources=[self.evaluations_table.table_arn]
            )
        )
        self.judge_model_id_param.grant_read(task_role)
        self.groundedness_evaluator_param.grant_read(task_role)
        for statement in model_invoke_statements(
            self, self._config.judge_model_id, ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
        ):
            task_role.add_to_principal_policy(statement)
        task_role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:Evaluate"],
                resources=[self.groundedness_evaluator.evaluator_arn],
            )
        )
        acknowledge_wildcards(
            task_definition,
            "ecr:GetAuthorizationToken no admite permisos por recurso, y el perfil de inferencia entre regiones "
            "exige el ARN del modelo base con región comodín (ADR-028).",
        )
        return task_definition, container

    def _state_machine(
        self, task_definition: ecs.FargateTaskDefinition, container: ecs.ContainerDefinition
    ) -> sfn.StateMachine:
        """ADR-031: flujo determinista con el estado de cada ejecución y sus errores."""
        mark_running = tasks.DynamoUpdateItem(
            self,
            "MarkRunning",
            table=self.evaluations_table,
            key={"evaluationId": tasks.DynamoAttributeValue.from_string(sfn.JsonPath.string_at("$.evaluationId"))},
            update_expression="SET #status = :status, executionArn = :execution",
            expression_attribute_names={"#status": "status"},
            expression_attribute_values={
                ":status": tasks.DynamoAttributeValue.from_string("RUNNING"),
                ":execution": tasks.DynamoAttributeValue.from_string(sfn.JsonPath.string_at("$$.Execution.Id")),
            },
            result_path=sfn.JsonPath.DISCARD,
        )

        run_evaluation = tasks.EcsRunTask(
            self,
            "RunEvaluationTask",
            integration_pattern=sfn.IntegrationPattern.RUN_JOB,
            cluster=self.cluster,
            task_definition=task_definition,
            launch_target=tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.LATEST),
            assign_public_ip=True,
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[self.security_group],
            container_overrides=[
                tasks.ContainerOverride(
                    container_definition=container,
                    environment=[
                        tasks.TaskEnvironmentVariable(
                            name="EVALUATION_ID", value=sfn.JsonPath.string_at("$.evaluationId")
                        )
                    ],
                )
            ],
            task_timeout=sfn.Timeout.duration(Duration.hours(1)),
            result_path=sfn.JsonPath.DISCARD,
        )

        mark_failed = tasks.DynamoUpdateItem(
            self,
            "MarkFailed",
            table=self.evaluations_table,
            key={"evaluationId": tasks.DynamoAttributeValue.from_string(sfn.JsonPath.string_at("$.evaluationId"))},
            update_expression="SET #status = :status, #error = :error",
            expression_attribute_names={"#status": "status", "#error": "error"},
            expression_attribute_values={
                ":status": tasks.DynamoAttributeValue.from_string("FAILED"),
                ":error": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.json_to_string(sfn.JsonPath.object_at("$.error"))
                ),
            },
            result_path=sfn.JsonPath.DISCARD,
        )
        run_evaluation.add_catch(mark_failed.next(sfn.Fail(self, "EvaluationFailed")), result_path="$.error")

        definition = mark_running.next(run_evaluation).next(sfn.Succeed(self, "EvaluationSucceeded"))

        log_group = logs.LogGroup(
            self,
            "StateMachineLogGroup",
            retention=retention(self._config.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )
        state_machine = sfn.StateMachine(
            self,
            "EvaluationStateMachine",
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.hours(2),
            logs=sfn.LogOptions(destination=log_group, level=sfn.LogLevel.ALL),
            tracing_enabled=False,
        )
        for rule in ("AwsSolutions-SF2", "Serverless-StepFunctionStateMachineXray"):
            acknowledge(state_machine, rule, "X-Ray queda como mejora futura de observabilidad (ADR-039).")
        acknowledge_wildcards(
            state_machine,
            "La integración .sync con ECS necesita las reglas administradas de EventBridge y cualquier revisión "
            "de la definición de tarea; así lo genera el construct EcsRunTask.",
        )
        return state_machine
