"""Endpoints de conversación: AgentCore administra la sesión; el Lambda reenvía el mensaje y registra el turno."""

import boto3
import pytest
from apitest import api_event, body_of

from api import create_conversation, get_conversation, list_conversations, send_message
from common import chat

TABLE = "conversaciones-test"


@pytest.fixture(autouse=True)
def conversations_table(monkeypatch):
    monkeypatch.setenv("CONVERSATIONS_TABLE_NAME", TABLE)
    boto3.client("dynamodb").create_table(
        TableName=TABLE,
        KeySchema=[{"AttributeName": "conversationId", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "conversationId", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "userId", "AttributeType": "S"},
            {"AttributeName": "updatedAt", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "byUser",
                "KeySchema": [
                    {"AttributeName": "userId", "KeyType": "HASH"},
                    {"AttributeName": "updatedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )


@pytest.fixture
def swarm(monkeypatch):
    """Simula el runtime de AgentCore y registra con qué sesión y payload se invocó."""
    calls = []

    def fake_invoke(session_id, user_id, prompt):
        calls.append({"session_id": session_id, "user_id": user_id, "prompt": prompt})
        # Sin sessionId, AgentCore crea la sesión y devuelve su id.
        session_id = session_id or f"agentcore-session-{len(calls):04d}-0123456789abcdef"
        return {
            "answer": "España fue campeón.\n\nFuentes: mundial-2026.md",
            "sources": [{"type": "document", "title": "mundial-2026.md", "uri": "s3://docs/mundial-2026.md"}],
            "agents": ["conversational_agent"],
            "blocked": False,
            "sessionId": session_id,
        }

    monkeypatch.setattr(chat, "invoke_swarm", fake_invoke)
    return calls


def start(content: str, context, user_id: str = "usuario-1"):
    return create_conversation.handler(
        api_event("POST", "/conversations", {"content": content}, user_id=user_id), context
    )


def follow_up(conversation_id: str, content: str, context, user_id: str = "usuario-1"):
    event = api_event(
        "POST",
        f"/conversations/{conversation_id}/messages",
        {"content": content},
        {"conversationId": conversation_id},
        user_id=user_id,
    )
    event["resource"] = "/conversations/{conversationId}/messages"
    return send_message.handler(event, context)


def detail(conversation_id: str, context, user_id: str = "usuario-1"):
    event = api_event(
        "GET", f"/conversations/{conversation_id}", None, {"conversationId": conversation_id}, user_id=user_id
    )
    event["resource"] = "/conversations/{conversationId}"
    return get_conversation.handler(event, context)


def test_first_message_returns_the_session_id_assigned_by_agentcore(swarm, context):
    first = start("¿Quién ganó el Mundial 2026?", context)

    assert first["statusCode"] == 201
    conversation_id = body_of(first)["conversationId"]
    # El primer mensaje se envía sin sessionId y la conversación toma el que asignó AgentCore.
    assert swarm[0]["session_id"] is None
    assert conversation_id == "agentcore-session-0001-0123456789abcdef"
    assert body_of(first)["message"]["sources"][0]["title"] == "mundial-2026.md"

    second = follow_up(conversation_id, "¿Y el tercer lugar?", context)

    assert second["statusCode"] == 200
    # El Lambda solo envía el mensaje: el contexto lo conserva la sesión del runtime.
    assert [call["session_id"] for call in swarm] == [None, conversation_id]
    assert swarm[1] == {"session_id": conversation_id, "user_id": "usuario-1", "prompt": "¿Y el tercer lugar?"}

    messages = body_of(detail(conversation_id, context))["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]


def test_users_only_see_their_own_conversations(swarm, context):
    mine = body_of(start("Hola", context, user_id="usuario-1"))["conversationId"]
    start("Hola", context, user_id="usuario-2")

    listing = body_of(list_conversations.handler(api_event("GET", "/conversations", user_id="usuario-1"), context))
    assert [c["conversationId"] for c in listing["conversations"]] == [mine]
    assert detail(mine, context, user_id="usuario-2")["statusCode"] == 404
    assert follow_up(mine, "Hola", context, user_id="usuario-2")["statusCode"] == 404


def test_follow_up_requires_an_existing_conversation(swarm, context):
    assert follow_up("sesion-inexistente-0123456789abcdefghij", "Hola", context)["statusCode"] == 404
    assert swarm == []


def test_first_message_failure_creates_nothing(monkeypatch, context):
    def broken_swarm(*_args):
        raise RuntimeError("runtime caído")

    monkeypatch.setattr(chat, "invoke_swarm", broken_swarm)

    response = start("Hola", context)

    assert response["statusCode"] == 502
    assert "runtime caído" not in response["body"]
    # Sin sesión asignada por AgentCore no hay conversación que registrar.
    listing = body_of(list_conversations.handler(api_event("GET", "/conversations"), context))["conversations"]
    assert listing == []


def test_follow_up_failure_returns_502_and_saves_error_message(swarm, monkeypatch, context):
    conversation_id = body_of(start("Hola", context))["conversationId"]

    def broken_swarm(*_args):
        raise RuntimeError("runtime caído")

    monkeypatch.setattr(chat, "invoke_swarm", broken_swarm)

    assert follow_up(conversation_id, "¿Sigues ahí?", context)["statusCode"] == 502
    assert body_of(detail(conversation_id, context))["messages"][-1]["error"] is True


@pytest.mark.parametrize("content", ["", "x" * 4001])
def test_message_length_is_validated(content, swarm, context):
    assert start(content, context)["statusCode"] == 400


def test_conversation_id_must_look_like_a_session_id(swarm, context):
    assert follow_up("corto", "Hola", context)["statusCode"] == 400


def test_invoke_sends_only_the_message_and_session(monkeypatch):
    import io
    import json

    from apitest import put_parameter
    from botocore.response import StreamingBody
    from botocore.stub import Stubber

    arn = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/swarm-abc"
    monkeypatch.setenv("RUNTIME_ARN_PARAM", "/test/agents/runtime-arn")
    put_parameter("/test/agents/runtime-arn", arn)
    session_id = "s" * 36
    raw = json.dumps({"answer": "hola", "sessionId": session_id}).encode()

    client = chat._agentcore_client()
    with Stubber(client) as stubber:
        stubber.add_response(
            "invoke_agent_runtime",
            {
                "response": StreamingBody(io.BytesIO(raw), len(raw)),
                "runtimeSessionId": session_id,
                "statusCode": 200,
                "contentType": "application/json",
            },
            {
                "agentRuntimeArn": arn,
                "runtimeSessionId": session_id,
                "contentType": "application/json",
                "accept": "application/json",
                "payload": json.dumps({"prompt": "hola", "actorId": "usuario-1"}).encode(),
            },
        )
        assert chat.invoke_swarm(session_id, "usuario-1", "hola")["answer"] == "hola"

        # El primer mensaje no envía runtimeSessionId y toma el que devuelve AgentCore.
        raw = json.dumps({"answer": "nuevo"}).encode()
        stubber.add_response(
            "invoke_agent_runtime",
            {
                "response": StreamingBody(io.BytesIO(raw), len(raw)),
                "runtimeSessionId": "asignado-por-agentcore-0123456789abcdef",
                "statusCode": 200,
                "contentType": "application/json",
            },
            {
                "agentRuntimeArn": arn,
                "contentType": "application/json",
                "accept": "application/json",
                "payload": json.dumps({"prompt": "nuevo", "actorId": "usuario-1"}).encode(),
            },
        )
        assert chat.invoke_swarm(None, "usuario-1", "nuevo")["sessionId"] == "asignado-por-agentcore-0123456789abcdef"


def test_agentcore_invocation_is_never_retried():
    # Un reintento volvería a ejecutar el swarm completo (doble costo y doble efecto en las herramientas).
    assert chat._agentcore_client().meta.config.retries["total_max_attempts"] == 1
