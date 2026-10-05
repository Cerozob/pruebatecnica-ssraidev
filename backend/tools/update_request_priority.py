"""Herramienta update_request_priority: Asigna el nivel de prioridad decidido por el LLM (ADR-022)."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    request_id = repo.require_text(event, "id")
    value = repo.require_choice(event, "priority", repo.LEVELS)
    return {"request": repo.update_field(request_id, "priority", value)}
