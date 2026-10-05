"""POST /evaluations: inicia una evaluación agéntica en Step Functions (paso 17, ADR-031)."""

import json
import time

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler.exceptions import ServiceError
from aws_lambda_powertools.logging import correlation_paths

from common import evaluations
from common.auth import require_admin
from common.http import build_resolver
from common.ids import new_id, now_iso
from common.settings import env

logger = Logger()
app = build_resolver()

_sfn = None


def _sfn_client():
    global _sfn
    if _sfn is None:
        _sfn = boto3.client("stepfunctions")
    return _sfn


class EvaluationInProgressError(ServiceError):
    def __init__(self):
        super().__init__(409, "Ya hay una evaluación en curso. Espera a que termine para iniciar otra.")


def _acquire_start_lock() -> None:
    """Candado de corta duración: dos clics simultáneos no pueden lanzar dos evaluaciones.

    No se libera: vence solo a los LOCK_SECONDS, porque ningún rol puede borrar elementos (ADR-021). Mientras
    tanto, la consulta a Step Functions ya ve la ejecución en curso.
    """
    now = int(time.time())
    try:
        evaluations.table().put_item(
            Item={"evaluationId": evaluations.START_LOCK_ID, "expiresAt": now + evaluations.LOCK_SECONDS},
            ConditionExpression="attribute_not_exists(evaluationId) OR expiresAt < :now",
            ExpressionAttributeValues={":now": now},
        )
    except evaluations.table().meta.client.exceptions.ConditionalCheckFailedException as error:
        raise EvaluationInProgressError() from error


def _execution_running(state_machine_arn: str) -> bool:
    running = _sfn_client().list_executions(stateMachineArn=state_machine_arn, statusFilter="RUNNING", maxResults=1)
    return bool(running.get("executions"))


@app.post("/evaluations")
def start_evaluation() -> tuple[dict, int]:
    require_admin(app)
    # Una evaluación a la vez, para no lanzar decenas por error (costo de modelos).
    state_machine_arn = env("EVALUATION_STATE_MACHINE_ARN")
    _acquire_start_lock()
    if _execution_running(state_machine_arn):
        raise EvaluationInProgressError()

    evaluation_id = new_id()
    item = {"evaluationId": evaluation_id, "status": "PENDING", "createdAt": now_iso()}
    evaluations.table().put_item(Item=item)

    _sfn_client().start_execution(
        stateMachineArn=state_machine_arn,
        name=evaluation_id,
        input=json.dumps({"evaluationId": evaluation_id}),
    )
    logger.info("Evaluación iniciada", extra={"evaluation_id": evaluation_id})
    return evaluations.summarize(item), 202


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
