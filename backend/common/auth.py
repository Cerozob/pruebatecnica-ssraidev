"""Identidad del usuario autenticado por el authorizer de Cognito de API Gateway."""

from aws_lambda_powertools.event_handler import APIGatewayRestResolver
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError


def current_user_id(app: APIGatewayRestResolver) -> str:
    """`sub` del ID token de Cognito; API Gateway ya validó el token."""
    claims = app.current_event.request_context.authorizer.claims or {}
    user_id = claims.get("sub")
    if not user_id:
        raise UnauthorizedError("Falta la identidad del usuario.")
    return user_id
