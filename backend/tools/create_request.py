"""Herramienta create_request: crea una solicitud solo con su descripción."""

from common import requests_repo as repo


@repo.tool_handler
def handler(event: dict) -> dict:
    return {"request": repo.create(repo.require_text(event, "description"))}
