"""Funciones puras del swarm: historial, reparto de herramientas y fuentes."""

import json
from dataclasses import dataclass

from swarm_agent.conversation import extract_sources, normalize_history, partition_tools


@dataclass
class FakeTool:
    tool_name: str


def test_history_starts_with_user_alternates_and_ends_with_assistant():
    history = [
        {"role": "assistant", "content": "hola"},
        {"role": "user", "content": "uno"},
        {"role": "user", "content": "dos"},
        {"role": "assistant", "content": "respuesta"},
        {"role": "user", "content": "sin respuesta"},
        {"role": "system", "content": "ignorado"},
    ]
    messages = normalize_history(history)
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[0]["content"][0]["text"] == "uno\n\ndos"


def test_tools_are_partitioned_by_gateway_target():
    tools = [
        FakeTool("conocimiento___Retrieve"),
        FakeTool("solicitudes-create-request___create_request"),
        FakeTool("busqueda-web___WebSearch"),
        FakeTool("otro___x"),
    ]
    conversational, specialists = partition_tools(
        tools, knowledge_target="conocimiento", web_search_target="busqueda-web", requests_target_prefix="solicitudes"
    )
    assert [t.tool_name for t in conversational] == [
        "conocimiento___Retrieve",
        "solicitudes-create-request___create_request",
    ]
    assert [t.tool_name for t in specialists] == ["busqueda-web___WebSearch"]


def test_sources_come_from_retrieval_and_web_search_results():
    kb_result = {
        "retrievalResults": [
            {
                "content": {"text": "España campeón"},
                "location": {"type": "S3", "s3Location": {"uri": "s3://b/ejemplos/mundial-2026.md"}},
            },
            {"content": {"text": "repetido"}, "location": {"s3Location": {"uri": "s3://b/ejemplos/mundial-2026.md"}}},
        ]
    }
    web_result = {"results": [{"title": "Amazon Aurora", "url": "https://docs.aws.amazon.com/aurora/"}]}
    messages = [
        {
            "role": "assistant",
            "content": [{"toolUse": {"toolUseId": "1", "name": "conocimiento___Retrieve", "input": {}}}],
        },
        {"role": "user", "content": [{"toolResult": {"toolUseId": "1", "content": [{"text": json.dumps(kb_result)}]}}]},
        {
            "role": "assistant",
            "content": [{"toolUse": {"toolUseId": "2", "name": "busqueda-web___WebSearch", "input": {}}}],
        },
        {"role": "user", "content": [{"toolResult": {"toolUseId": "2", "content": [{"json": web_result}]}}]},
    ]
    sources = extract_sources(messages, knowledge_target="conocimiento", web_search_target="busqueda-web")
    assert [(s["type"], s["title"]) for s in sources] == [("document", "mundial-2026.md"), ("web", "Amazon Aurora")]
    assert sources[0]["excerpt"] == "España campeón"


def test_results_of_other_tools_are_not_sources():
    messages = [
        {
            "role": "assistant",
            "content": [{"toolUse": {"toolUseId": "1", "name": "solicitudes-get-request___get_request", "input": {}}}],
        },
        {
            "role": "user",
            "content": [{"toolResult": {"toolUseId": "1", "content": [{"json": {"url": "https://x.com"}}]}}],
        },
    ]
    assert extract_sources(messages, knowledge_target="conocimiento", web_search_target="busqueda-web") == []
