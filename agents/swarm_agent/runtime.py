"""Punto de entrada del swarm en AgentCore Runtime (paso 10, ADR-015).

El llamador solo envía el mensaje (y el sessionId para continuar una conversación); el contexto lo
administra el runtime con su sesión y AgentCore Memory (ver swarm_agent/memory.py).
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp, RequestContext

from swarm_agent.memory import ConversationMemory
from swarm_agent.settings import AgentSettings, param
from swarm_agent.swarm import gateway_client, list_all_tools, run_turn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("swarm_agent")

app = BedrockAgentCoreApp()

MAX_PROMPT_LENGTH = 4000
# Actor por defecto si el llamador no identifica al usuario (por ejemplo, pruebas manuales).
DEFAULT_ACTOR = "anonimo"

_memory: ConversationMemory | None = None


def conversation_memory(region: str) -> ConversationMemory:
    global _memory
    if _memory is None:
        _memory = ConversationMemory(param("MEMORY_ID_PARAM"), region)
    return _memory


@app.entrypoint
def invoke(payload: dict, context: RequestContext) -> dict:
    prompt = (payload.get("prompt") or "").strip()
    if not prompt or len(prompt) > MAX_PROMPT_LENGTH:
        return {"error": f"El mensaje debe tener entre 1 y {MAX_PROMPT_LENGTH} caracteres."}
    # AgentCore Runtime siempre envía el sessionId: el del llamador o uno nuevo que crea el servicio si el
    # llamador lo omite. Solo falta al llamar al contenedor directamente, fuera del servicio.
    session_id = context.session_id
    if not session_id:
        return {"error": "Falta el sessionId de AgentCore Runtime."}
    actor_id = payload.get("actorId") or DEFAULT_ACTOR

    settings = AgentSettings.load()
    memory = conversation_memory(settings.region)
    history = memory.history(actor_id, session_id)

    # session.id agrupa las trazas de la conversación en la observabilidad de AgentCore (paso 24).
    trace_attributes = {"session.id": session_id}
    with gateway_client(settings) as mcp:
        tools = list_all_tools(mcp)
        result = run_turn(settings, tools, prompt, history, trace_attributes)

    # Todo turno se guarda, también los bloqueados, para auditoría. En un bloqueo, la respuesta guardada es el
    # mensaje del guardrail: la salida original del modelo no existe porque el guardrail evalúa la entrada.
    memory.append_turn(actor_id, session_id, prompt, result.answer)
    logger.info("Turno completado", extra={"agents": result.agents, "blocked": result.blocked})
    return {**result.to_dict(), "sessionId": session_id}


if __name__ == "__main__":
    app.run()
