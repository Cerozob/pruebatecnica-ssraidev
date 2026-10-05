"""Identidad del usuario autenticado por el authorizer de Cognito de API Gateway."""

import os

from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import ForbiddenError, UnauthorizedError

DEFAULT_ADMINS_GROUP = "admins"


def _claims(app: APIGatewayRestResolver) -> dict:
    return app.current_event.request_context.authorizer.claims or {}


def current_user_id(app: APIGatewayRestResolver) -> str:
    """`sub` del ID token de Cognito; API Gateway ya validó el token."""
    user_id = _claims(app).get("sub")
    if not user_id:
        raise UnauthorizedError("Falta la identidad del usuario.")
    return user_id


def user_groups(app: APIGatewayRestResolver) -> set[str]:
    """Grupos de Cognito del usuario (claim `cognito:groups`).

    El authorizer de API Gateway REST entrega el claim como texto: "admins" o "admins,users". Se aceptan
    también la forma "[admins users]" y una lista, por si el formato cambia.
    """
    raw = _claims(app).get("cognito:groups") or ""
    if isinstance(raw, list):
        return {str(group).strip() for group in raw if str(group).strip()}
    return {group for group in raw.strip("[]").replace(",", " ").split() if group}


def require_admin(app: APIGatewayRestResolver) -> None:
    """ADR-043: el visor de logs y las evaluaciones son solo para el grupo de administradores."""
    if os.environ.get("ADMINS_GROUP", DEFAULT_ADMINS_GROUP) not in user_groups(app):
        raise ForbiddenError("Esta función es solo para administradores.")
