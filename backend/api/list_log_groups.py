"""GET /logs/groups: log groups de CloudWatch con las etiquetas de la aplicación (pasos 25-26)."""

from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from common.http import build_resolver
from common.log_viewer import list_tagged_log_groups, log_group_id

logger = Logger()
app = build_resolver()


@app.get("/logs/groups")
def list_log_groups() -> dict:
    # El id va en la ruta de los eventos; el nombre tiene barras (ver get_log_events.py).
    return {"logGroups": [{"name": name, "id": log_group_id(name)} for name in list_tagged_log_groups()]}


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
