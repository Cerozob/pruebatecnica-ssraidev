"""Swarm de Strands con tres agentes y herramientas del gateway MCP de AgentCore (pasos 10-16)."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import boto3
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.multiagent import Swarm
from strands.tools.mcp import MCPClient

from swarm_agent.conversation import extract_sources, normalize_history, partition_tools
from swarm_agent.guardrail import contains_prompt_attack
from swarm_agent.settings import AgentSettings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"

CONVERSATIONAL = "conversational_agent"
MODERNIZATION = "modernization_agent"
CLOUD_RECOMMENDER = "cloud_recommender_agent"
GUARDRAIL_STOP_REASON = "guardrail_intervened"


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


@dataclass
class TurnResult:
    answer: str
    blocked: bool
    agents: list[str]
    sources: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"answer": self.answer, "blocked": self.blocked, "agents": self.agents, "sources": self.sources}


def gateway_client(settings: AgentSettings) -> MCPClient:
    """Cliente MCP del gateway con autenticación IAM (SigV4) usando el rol del proceso."""
    return MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=settings.gateway_url, aws_region=settings.region, aws_service="bedrock-agentcore"
        )
    )


def list_all_tools(mcp: MCPClient) -> list:
    """Todas las herramientas del gateway, recorriendo la paginación de MCP."""
    tools: list = []
    token = None
    while True:
        page = mcp.list_tools_sync(pagination_token=token)
        tools.extend(page)
        token = getattr(page, "pagination_token", None)
        if not token:
            return tools


def _model(settings: AgentSettings) -> BedrockModel:
    # ADR-026: Strands aplica el guardrail en cada invocación del modelo. De la entrada solo se evalúa el último
    # mensaje del usuario, para que el historial o los resultados de herramientas no lo disparen. Si el
    # guardrail interviene, la entrada y la salida se reemplazan por el mensaje de bloqueo. La respuesta final
    # se revisa aparte en run_turn, porque el filtro de ataques de prompt no evalúa la salida.
    return BedrockModel(
        model_id=settings.model_id,
        region_name=settings.region,
        temperature=0.2,
        max_tokens=4096,
        guardrail_id=settings.guardrail_id,
        guardrail_version=settings.guardrail_version,
        guardrail_trace="enabled",
        guardrail_latest_message=True,
        guardrail_redact_input=True,
        guardrail_redact_input_message=settings.blocked_message,
        guardrail_redact_output=True,
        guardrail_redact_output_message=settings.blocked_message,
    )


def build_agents(
    settings: AgentSettings, tools: list, history: list[dict], trace_attributes: dict | None = None
) -> dict[str, Agent]:
    conversational_tools, specialist_tools = partition_tools(
        tools,
        knowledge_target=settings.knowledge_target,
        web_search_target=settings.web_search_target,
        requests_target_prefix=settings.requests_target_prefix,
    )
    messages = normalize_history(history)

    def agent(name: str, prompt: str, description: str, agent_tools: list) -> Agent:
        return Agent(
            name=name,
            description=description,
            system_prompt=load_prompt(prompt),
            model=_model(settings),
            tools=agent_tools,
            # Cada agente recibe el historial, porque el swarm le pasa solo la tarea y el mensaje de traspaso.
            messages=[dict(message, content=[dict(block) for block in message["content"]]) for message in messages],
            callback_handler=None,
            trace_attributes=trace_attributes,
        )

    return {
        CONVERSATIONAL: agent(
            CONVERSATIONAL,
            "conversational",
            "Dialoga con el usuario, gestiona solicitudes y responde desde la base de conocimiento.",
            conversational_tools,
        ),
        MODERNIZATION: agent(
            MODERNIZATION,
            "modernization",
            "Especialista en recomendaciones de modernización de aplicaciones.",
            specialist_tools,
        ),
        CLOUD_RECOMMENDER: agent(
            CLOUD_RECOMMENDER,
            "cloud_recommender",
            "Especialista en recomendar servicios cloud de AWS y Azure.",
            specialist_tools,
        ),
    }


def run_turn(
    settings: AgentSettings,
    tools: list,
    prompt: str,
    history: list[dict],
    trace_attributes: dict | None = None,
) -> TurnResult:
    """Ejecuta un turno de conversación en el swarm y devuelve la respuesta del último agente."""
    agents = build_agents(settings, tools, history, trace_attributes)
    swarm = Swarm(
        list(agents.values()),
        entry_point=agents[CONVERSATIONAL],
        max_handoffs=6,
        max_iterations=10,
        # Por debajo de la espera de 280 s del Lambda de chat, para que todo turno llegue al historial.
        execution_timeout=240.0,
        node_timeout=240.0,
        repetitive_handoff_detection_window=6,
        repetitive_handoff_min_unique_agents=2,
        trace_attributes=trace_attributes,
    )
    result = swarm(prompt)

    visited = [node.node_id for node in result.node_history]
    final_node = visited[-1] if visited else CONVERSATIONAL
    final = result.results.get(final_node)
    agent_result = getattr(final, "result", None)

    blocked = any(
        getattr(getattr(node_result, "result", None), "stop_reason", None) == GUARDRAIL_STOP_REASON
        for node_result in result.results.values()
    )
    if blocked:
        logger.warning("El guardrail bloqueó la solicitud")
        return TurnResult(answer=settings.blocked_message, blocked=True, agents=visited)

    if isinstance(agent_result, Exception) or agent_result is None:
        raise RuntimeError(f"El swarm terminó sin respuesta (estado {result.status})")

    # ADR-026: la respuesta también pasa por el filtro de ataques de prompt, por si una instrucción inyectada
    # desde la web o la base de conocimiento llegó a la salida del modelo.
    answer = str(agent_result).strip()
    bedrock = boto3.client("bedrock-runtime", region_name=settings.region)
    if contains_prompt_attack(bedrock, settings.guardrail_id, settings.guardrail_version, answer):
        logger.warning("El guardrail bloqueó la respuesta del modelo")
        return TurnResult(answer=settings.blocked_message, blocked=True, agents=visited)

    sources = []
    for agent in agents.values():
        sources.extend(
            extract_sources(
                agent.messages,
                knowledge_target=settings.knowledge_target,
                web_search_target=settings.web_search_target,
            )
        )
    unique = {source["uri"]: source for source in reversed(sources)}
    return TurnResult(answer=answer, blocked=False, agents=visited, sources=list(unique.values()))
