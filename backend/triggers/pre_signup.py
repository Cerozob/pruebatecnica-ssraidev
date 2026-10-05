"""Trigger Pre SignUp de Cognito: solo correos o dominios autorizados pueden registrarse (ADR-007)."""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters

from common.settings import CACHE_SECONDS, env

logger = Logger()

REJECTION_MESSAGE = "Tu correo no está autorizado para registrarse en el asistente."


def is_allowed(email: str, allowlist: dict) -> bool:
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1]
    emails = {item.strip().lower() for item in allowlist.get("emails", [])}
    domains = {item.strip().lower().lstrip("@") for item in allowlist.get("domains", [])}
    return email in emails or domain in domains


@logger.inject_lambda_context
def handler(event, context):
    email = event.get("request", {}).get("userAttributes", {}).get("email", "")
    # ADR-027: la lista vive en Secrets Manager; se cachea unos minutos.
    allowlist = parameters.get_secret(env("ALLOWLIST_SECRET_ARN"), transform="json", max_age=CACHE_SECONDS)
    if not is_allowed(email, allowlist):
        logger.warning("Registro rechazado", extra={"trigger_source": event.get("triggerSource")})
        raise PermissionError(REJECTION_MESSAGE)
    logger.info("Registro autorizado", extra={"trigger_source": event.get("triggerSource")})
    return event
