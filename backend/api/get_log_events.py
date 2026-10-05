"""GET /logs/groups/{logGroupId}/events: eventos de un log group como texto plano (pasos 25-26).

El nombre de un log group tiene barras. API Gateway REST decodifica los parámetros de la ruta antes de
pasarlos al backend, así que la ruta lleva el nombre en base64url (`logGroupId`), que no se altera.
"""

import time
from collections import deque
from datetime import UTC, datetime
from typing import Annotated

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from aws_lambda_powertools.event_handler.openapi.params import Path, Query
from aws_lambda_powertools.logging import correlation_paths

from common.http import build_resolver
from common.log_viewer import is_app_log_group, log_group_name, logs_client

logger = Logger()
app = build_resolver()

MAX_PAGES = 10


def format_event(event: dict) -> str:
    timestamp = datetime.fromtimestamp(event["timestamp"] / 1000, tz=UTC).isoformat(timespec="milliseconds")
    return f"{timestamp} {event['message'].rstrip()}"


@app.get("/logs/groups/<logGroupId>/events")
def get_log_events(
    logGroupId: Annotated[str, Path(min_length=1, max_length=1400, pattern=r"^[A-Za-z0-9_-]+$")],
    hours: Annotated[int, Query(ge=1, le=168, description="Horas hacia atrás")] = 24,
    limit: Annotated[int, Query(ge=1, le=1000, description="Máximo de eventos")] = 200,
):
    name = log_group_name(logGroupId)
    arn_parts = app.lambda_context.invoked_function_arn.split(":")
    region, account = arn_parts[3], arn_parts[4]
    if name is None or not is_app_log_group(name, region, account):
        raise NotFoundError("El log group no existe o no pertenece a la aplicación.")

    # FilterLogEvents devuelve primero los más antiguos; se recorren unas páginas y se conservan los últimos.
    latest: deque[str] = deque(maxlen=limit)
    kwargs = {"logGroupName": name, "startTime": int((time.time() - hours * 3600) * 1000)}
    for _ in range(MAX_PAGES):
        response = logs_client().filter_log_events(**kwargs)
        latest.extend(format_event(event) for event in response.get("events", []))
        if not response.get("nextToken"):
            break
        kwargs["nextToken"] = response["nextToken"]
    return Response(status_code=200, content_type=content_types.TEXT_PLAIN, body="\n".join(latest))


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
