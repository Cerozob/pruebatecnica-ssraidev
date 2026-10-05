"""Contexto corto de la conversación, administrado por AgentCore por sessionId.

AgentCore Runtime mantiene un microVM por sesión: mientras la sesión está activa, el historial vive en
memoria del proceso. Como el microVM se detiene tras 15 minutos de inactividad, cada turno también se
guarda en la memoria de corto plazo de AgentCore Memory, y se recupera de ahí cuando la sesión se reanuda.
Los multi-agentes de Strands no persisten el historial de cada agente, por eso se guarda aquí.
"""

from collections.abc import Iterable
from typing import Any

# Cantidad máxima de mensajes previos que recibe el swarm como contexto.
MAX_HISTORY_MESSAGES = 40
_MAX_EVENTS = 200

_ROLES = {"USER": "user", "ASSISTANT": "assistant"}


def messages_from_events(events: Iterable[Any]) -> list[dict]:
    """Convierte los eventos de AgentCore Memory (en orden cronológico) en mensajes {role, content}."""
    messages: list[dict] = []
    for event in events:
        for item in event.get("payload", []) or []:
            conversational = item.get("conversational")
            if not conversational:
                continue
            role = _ROLES.get(conversational.get("role", ""))
            text = (conversational.get("content") or {}).get("text", "")
            if role and text:
                messages.append({"role": role, "content": text})
    return messages[-MAX_HISTORY_MESSAGES:]


class ConversationMemory:
    """Historial por sesión: caché en el proceso del microVM, con AgentCore Memory como respaldo durable."""

    def __init__(self, memory_id: str, region: str) -> None:
        # Importación diferida: las pruebas de las funciones puras no necesitan el SDK.
        from bedrock_agentcore.memory import MemorySessionManager

        self._manager = MemorySessionManager(memory_id=memory_id, region_name=region)
        self._cache: dict[str, list[dict]] = {}

    def history(self, actor_id: str, session_id: str) -> list[dict]:
        if session_id not in self._cache:
            events = self._manager.list_events(actor_id=actor_id, session_id=session_id, max_results=_MAX_EVENTS)
            self._cache[session_id] = messages_from_events(events)
        return list(self._cache[session_id])

    def append_turn(self, actor_id: str, session_id: str, prompt: str, answer: str) -> None:
        from bedrock_agentcore.memory.constants import ConversationalMessage, MessageRole

        self._manager.add_turns(
            actor_id=actor_id,
            session_id=session_id,
            messages=[
                ConversationalMessage(prompt, MessageRole.USER),
                ConversationalMessage(answer, MessageRole.ASSISTANT),
            ],
        )
        cached = self._cache.setdefault(session_id, [])
        cached.extend([{"role": "user", "content": prompt}, {"role": "assistant", "content": answer}])
        del cached[:-MAX_HISTORY_MESSAGES]
