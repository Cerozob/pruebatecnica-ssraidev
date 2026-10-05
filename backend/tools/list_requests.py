"""Herramienta list_requests: lista las solicitudes, con filtro opcional por estado."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    status = repo.require_choice(event, "status", repo.STATUSES) if event.get("status") else None
    requests = repo.list_all(status)
    return {"requests": requests, "count": len(requests)}
