"""Herramienta get_request: consulta una solicitud por su id."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    return {"request": repo.get(repo.require_text(event, "id"))}
