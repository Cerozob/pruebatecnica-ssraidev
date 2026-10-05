"""Resolver HTTP de Powertools compartido por todos los endpoints de la API."""

import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, CORSConfig, Response, content_types
from aws_lambda_powertools.event_handler.exceptions import NotFoundError, ServiceError
from aws_lambda_powertools.event_handler.openapi.exceptions import RequestValidationError

logger = Logger()


def _cors() -> CORSConfig:
    origins = [origin for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin]
    return CORSConfig(
        allow_origin=origins[0] if origins else "*",
        extra_origins=origins[1:],
        allow_headers=["Authorization", "Content-Type"],
    )


def build_resolver() -> APIGatewayRestResolver:
    """Resolver con validación de entradas y errores con un formato JSON uniforme."""
    app = APIGatewayRestResolver(cors=_cors(), enable_validation=True)

    @app.exception_handler(RequestValidationError)
    def _validation_error(error: RequestValidationError) -> Response:
        details = [
            {"field": ".".join(str(part) for part in item.get("loc", [])), "message": item.get("msg", "")}
            for item in error.errors()
        ]
        return _error(400, "La petición no cumple el esquema esperado.", details)

    @app.exception_handler(NotFoundError)
    def _not_found(error: NotFoundError) -> Response:
        return _error(404, str(error.msg) or "El recurso no existe.")

    @app.exception_handler(ServiceError)
    def _service_error(error: ServiceError) -> Response:
        return _error(error.status_code, error.msg)

    @app.exception_handler(Exception)
    def _unexpected(error: Exception) -> Response:
        # El detalle va a CloudWatch; al cliente solo un mensaje genérico, para no filtrar información interna.
        logger.exception("Error no controlado")
        return _error(500, "Error interno.")

    return app


def _error(status: int, message: str, details: list | None = None) -> Response:
    body = {"message": message}
    if details:
        body["details"] = details
    return Response(status_code=status, content_type=content_types.APPLICATION_JSON, body=body)
