"""Conversión de eventos de AgentCore Memory al historial del swarm."""

from swarm_agent.conversation import normalize_history
from swarm_agent.memory import MAX_HISTORY_MESSAGES, messages_from_events


def event(*messages):
    return {"payload": [{"conversational": {"role": role, "content": {"text": text}}} for role, text in messages]}


def test_events_become_alternating_messages():
    events = [
        event(("USER", "¿Quién ganó?"), ("ASSISTANT", "España.")),
        event(("USER", "¿Y el tercero?"), ("ASSISTANT", "Inglaterra.")),
        {"payload": [{"blob": "ignorado"}]},
    ]
    messages = messages_from_events(events)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages[-1]["content"] == "Inglaterra."
    # El resultado es un historial válido para Bedrock.
    assert len(normalize_history(messages)) == 4


def test_history_is_limited_to_the_most_recent_messages():
    events = [event(("USER", f"pregunta {i}"), ("ASSISTANT", f"respuesta {i}")) for i in range(50)]
    messages = messages_from_events(events)
    assert len(messages) == MAX_HISTORY_MESSAGES
    assert messages[-1]["content"] == "respuesta 49"
