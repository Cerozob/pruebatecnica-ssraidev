"""Trigger Post Confirmation de Cognito: todo usuario nuevo entra al grupo de usuarios normales (ADR-043).

El grupo de administradores nunca se asigna aquí: se asigna a mano en la consola de Cognito, a propósito.
"""

import boto3
from aws_lambda_powertools import Logger

from common.settings import env

logger = Logger()

_cognito = None


def _cognito_client():
    global _cognito
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _cognito


@logger.inject_lambda_context
def handler(event, context):
    # El trigger también se ejecuta al confirmar un cambio de contraseña; solo interesa el registro.
    if event.get("triggerSource") != "PostConfirmation_ConfirmSignUp":
        return event
    _cognito_client().admin_add_user_to_group(
        UserPoolId=event["userPoolId"], Username=event["userName"], GroupName=env("DEFAULT_GROUP")
    )
    logger.info("Usuario agregado al grupo por defecto", extra={"group": env("DEFAULT_GROUP")})
    return event
