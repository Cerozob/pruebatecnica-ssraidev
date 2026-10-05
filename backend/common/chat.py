"""Turnos de conversación: reenvía el mensaje al runtime de AgentCore y registra el turno (pasos 8-9).

El Lambda no arma contexto ni historial. AgentCore Runtime administra la sesión: si la invocación no
lleva `runtimeSessionId`, el servicio crea una sesión nueva y devuelve su id en la respuesta, y con ese
mismo id las invocaciones siguientes llegan al mismo contexto.
"""

import json

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import ServiceError
from botocore.config import Config

from common import conversations
from common.settings import param

logger = Logger(child=True)

_agentcore = None


def _agentcore_client():
    global _agentcore
    if _agentcore is None:
        _agentcore = boto3.client(
            "bedrock-agentcore",
            config=Config(read_timeout=280, connect_timeout=10, retries={"max_attempts": 1}),
        )
    return _agentcore


def invoke_swarm(session_id: str | None, user_id: str, prompt: str) -> dict:
    """Invoca el runtime de forma síncrona y devuelve su respuesta con el `sessionId` de AgentCore.

    Sin `session_id`, AgentCore crea la sesión y devuelve su id en `runtimeSessionId`.
    """
    request = {
        "agentRuntimeArn": param("RUNTIME_ARN_PARAM"),
        "contentType": "application/json",
        "accept": "application/json",
        "payload": json.dumps({"prompt": prompt, "actorId": user_id}).encode(),
    }
    if session_id:
        request["runtimeSessionId"] = session_id
    response = _agentcore_client().invoke_agent_runtime(**request)
    body = json.loads(response["response"].read())
    if "error" in body:
        raise RuntimeError(body["error"])
    return {**body, "sessionId": response["runtimeSessionId"]}


def _assistant_message(conversation_id: str, result: dict) -> dict:
    return conversations.add_message(
        conversation_id,
        "assistant",
        result.get("answer", ""),
        sources=result.get("sources") or None,
        agents=result.get("agents") or None,
        blocked=bool(result.get("blocked")),
    )


def start_conversation(user_id: str, content: str) -> dict:
    """Primer mensaje: AgentCore asigna la sesión y su id pasa a ser el id de la conversación."""
    try:
        result = invoke_swarm(None, user_id, content)
    except Exception as error:
        logger.exception("Falló la invocación del swarm")
        raise ServiceError(502, "El asistente no pudo responder.") from error

    conversation_id = result["sessionId"]
    logger.append_keys(conversation_id=conversation_id)
    conversations.create_conversation(conversation_id, user_id, content)
    user_message = conversations.add_message(conversation_id, "user", content)
    assistant_message = _assistant_message(conversation_id, result)
    return {"conversationId": conversation_id, "userMessage": user_message, "message": assistant_message}


def continue_conversation(conversation_id: str, user_id: str, content: str) -> dict:
    """Mensaje siguiente: se invoca la misma sesión, que ya tiene el contexto."""
    user_message = conversations.add_message(conversation_id, "user", content)
    try:
        result = invoke_swarm(conversation_id, user_id, content)
    except Exception as error:
        logger.exception("Falló la invocación del swarm")
        # Se guarda el fallo para que el frontend deje de esperar la respuesta.
        conversations.add_message(
            conversation_id, "assistant", "No pude procesar tu mensaje. Intenta de nuevo.", error=True
        )
        raise ServiceError(502, "El asistente no pudo responder.") from error

    assistant_message = _assistant_message(conversation_id, result)
    conversations.touch_conversation(conversation_id)
    return {"conversationId": conversation_id, "userMessage": user_message, "message": assistant_message}
