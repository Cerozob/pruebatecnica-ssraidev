"""Herramienta update_request_summary: guarda el resumen ejecutivo de una solicitud."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    request_id = repo.require_text(event, "id")
    summary = repo.require_text(event, "summary")
    if summary == repo.get(request_id)["description"].strip():
        raise repo.ToolInputError("El resumen debe ser distinto de la descripción.")
    return {"request": repo.update_field(request_id, "summary", summary)}
