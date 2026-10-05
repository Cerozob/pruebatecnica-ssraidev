"""Herramienta update_request_status: Cambia el estado de una solicitud (pending, in progress, delayed o done)."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    request_id = repo.require_text(event, "id")
    value = repo.require_choice(event, "status", repo.STATUSES)
    return {"request": repo.update_field(request_id, "status", value)}
