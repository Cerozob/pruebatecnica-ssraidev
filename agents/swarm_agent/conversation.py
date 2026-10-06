"""Funciones puras del swarm: historial, reparto de herramientas y extracción de fuentes.

No importan Strands para poder probarlas sin dependencias pesadas.
"""

import json
from collections.abc import Iterable
from datetime import date
from pathlib import PurePosixPath
from typing import Any

TOOL_SEPARATOR = "___"


def with_current_date(prompt: str, today: date) -> str:
    """Agrega la fecha actual al prompt de sistema.

    Sin ella, el modelo trata como futuros los hechos posteriores a su entrenamiento (por ejemplo, el Mundial 2026).
    """
    return f"{prompt.rstrip()}\n\nFecha actual: {today.isoformat()}.\n"


def normalize_history(history: Iterable[dict]) -> list[dict]:
    """Convierte el historial guardado en mensajes de Bedrock válidos.

    Bedrock exige que la conversación empiece por el usuario y alterne roles; el turno nuevo
    lo agrega el swarm, así que el historial debe terminar con el asistente.
    """
    messages: list[dict] = []
    for turn in history:
        role, text = turn.get("role"), (turn.get("content") or "").strip()
        if role not in ("user", "assistant") or not text:
            continue
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"][0]["text"] += f"\n\n{text}"
        else:
            messages.append({"role": role, "content": [{"text": text}]})
    while messages and messages[0]["role"] != "user":
        messages.pop(0)
    while messages and messages[-1]["role"] != "assistant":
        messages.pop()
    return messages


def target_of(tool_name: str) -> str:
    """El gateway nombra cada herramienta como "<destino>___<herramienta>"."""
    return tool_name.split(TOOL_SEPARATOR, 1)[0]


def partition_tools(
    tools: Iterable[Any], *, knowledge_target: str, web_search_target: str, requests_target_prefix: str
) -> tuple[list[Any], list[Any]]:
    """Reparte las herramientas del gateway entre el agente conversacional y los especialistas (ADR-014, ADR-023).

    Devuelve (herramientas del conversacional, herramientas de los especialistas).
    """
    conversational, specialists = [], []
    for tool in tools:
        target = target_of(tool.tool_name)
        if target == knowledge_target or target.startswith(f"{requests_target_prefix}-"):
            conversational.append(tool)
        elif target == web_search_target:
            specialists.append(tool)
    return conversational, specialists


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _parse_tool_result(content: list[dict]) -> list[Any]:
    parsed: list[Any] = []
    for block in content:
        if "json" in block:
            parsed.append(block["json"])
        elif "text" in block:
            try:
                parsed.append(json.loads(block["text"]))
            except TypeError, ValueError:
                continue
    return parsed


def _document_sources(payload: Any) -> list[dict]:
    sources = []
    for node in _walk(payload):
        location = node.get("location")
        if not isinstance(location, dict):
            continue
        uri = None
        for candidate in _walk(location):
            uri = candidate.get("uri") or candidate.get("url")
            if uri:
                break
        if not uri:
            continue
        text = (node.get("content") or {}).get("text", "") if isinstance(node.get("content"), dict) else ""
        sources.append({"type": "document", "title": PurePosixPath(uri).name or uri, "uri": uri, "excerpt": text[:300]})
    return sources


def _web_sources(payload: Any) -> list[dict]:
    sources = []
    for node in _walk(payload):
        url = node.get("url")
        if isinstance(url, str) and url.startswith("http"):
            sources.append({"type": "web", "title": node.get("title") or url, "uri": url, "excerpt": ""})
    return sources


def extract_sources(messages: Iterable[dict], *, knowledge_target: str, web_search_target: str) -> list[dict]:
    """Obtiene las fuentes de los resultados de las herramientas de recuperación y búsqueda web."""
    tool_names: dict[str, str] = {}
    sources: list[dict] = []
    for message in messages:
        for block in message.get("content", []):
            if "toolUse" in block:
                tool_names[block["toolUse"]["toolUseId"]] = block["toolUse"]["name"]
            elif "toolResult" in block:
                result = block["toolResult"]
                target = target_of(tool_names.get(result.get("toolUseId", ""), ""))
                for payload in _parse_tool_result(result.get("content", [])):
                    if target == knowledge_target:
                        sources.extend(_document_sources(payload))
                    elif target == web_search_target:
                        sources.extend(_web_sources(payload))

    unique: dict[str, dict] = {}
    for source in sources:
        unique.setdefault(source["uri"], source)
    return list(unique.values())
