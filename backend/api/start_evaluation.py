"""POST /evaluations: inicia una evaluación agéntica en Step Functions (paso 17, ADR-031)."""

import json

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.logging import correlation_paths

from common import evaluations
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


@app.post("/evaluations")
def start_evaluation() -> tuple[dict, int]:
    evaluation_id = new_id()
    item = {"evaluationId": evaluation_id, "status": "PENDING", "createdAt": now_iso()}
    evaluations.table().put_item(Item=item)

    _sfn_client().start_execution(
        stateMachineArn=env("EVALUATION_STATE_MACHINE_ARN"),
        name=evaluation_id,
        input=json.dumps({"evaluationId": evaluation_id}),
    )
    logger.info("Evaluación iniciada", extra={"evaluation_id": evaluation_id})
    return evaluations.summarize(item), 202


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_REST)
def handler(event, context):
    return app.resolve(event, context)
