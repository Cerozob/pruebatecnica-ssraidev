"""Tarea de evaluación agéntica en Fargate: Strands Evals y AgentCore Evaluations con un modelo juez (paso 17).

Ejecuta el mismo swarm que el runtime, en proceso, para capturar sus trazas OpenTelemetry completas
y entregarlas al evaluador de groundedness de AgentCore.
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from bedrock_agentcore.evaluation import create_strands_evaluator
from strands.models import BedrockModel
from strands_evals.evaluators import OutputEvaluator
from strands_evals.telemetry import StrandsEvalsTelemetry
from strands_evals.types import EvaluationData

from evaluation.scoring import (
    ACCURACY,
    GROUNDEDNESS_PASS_SCORE,
    EvalCase,
    case_passed,
    groundedness_result,
    injection_score,
    load_cases,
    load_rubric,
    summarize,
)
from swarm_agent.settings import AgentSettings, param
from swarm_agent.swarm import gateway_client, list_all_tools, run_turn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("evaluation")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dynamo(value):
    """DynamoDB no acepta float: se convierte a Decimal pasando por JSON."""
    return json.loads(json.dumps(value), parse_float=Decimal)


class EvaluationStore:
    def __init__(self, evaluation_id: str):
        self.evaluation_id = evaluation_id
        self.table = boto3.resource("dynamodb").Table(os.environ["EVALUATIONS_TABLE_NAME"])

    def update(self, **fields) -> None:
        names = {f"#{key}": key for key in fields}
        values = {f":{key}": _dynamo(value) for key, value in fields.items()}
        self.table.update_item(
            Key={"evaluationId": self.evaluation_id},
            UpdateExpression="SET " + ", ".join(f"#{key} = :{key}" for key in fields),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )


class Evaluator:
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        judge = BedrockModel(model_id=param("JUDGE_MODEL_ID_PARAM"), region_name=settings.region, temperature=0)
        # Strands Evals: precisión e información insuficiente, calificadas por el juez.
        self.accuracy = OutputEvaluator(rubric=load_rubric("accuracy_rubric"), model=judge, name="precision")
        self.insufficient = OutputEvaluator(
            rubric=load_rubric("insufficient_information_rubric"), model=judge, name="informacion_insuficiente"
        )
        # AgentCore Evaluations: groundedness sobre las trazas del swarm, con el mismo juez.
        self.groundedness = create_strands_evaluator(
            param("GROUNDEDNESS_EVALUATOR_ID_PARAM"),
            region=settings.region,
            test_pass_score=GROUNDEDNESS_PASS_SCORE,
        )
        self.telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()

    def run_case(self, case: EvalCase, tools: list) -> dict:
        self.telemetry.in_memory_exporter.clear()
        trace_attributes = {"session.id": f"evaluation-{case.id}"}
        try:
            turn = run_turn(self.settings, tools, case.question, [], trace_attributes)
        except Exception as error:
            logger.exception("El caso %s falló al ejecutar el swarm", case.id)
            return self._result(case, answer="", agents=[], score=0.0, reason=f"Error del swarm: {error}")

        if case.category == "prompt_injection":
            score, reason = injection_score(turn.blocked, turn.answer, self.settings.blocked_message)
            return self._result(case, turn.answer, turn.agents, score, reason, blocked=turn.blocked)

        data = EvaluationData(
            input=case.question,
            actual_output=turn.answer,
            expected_output=case.expected,
            actual_trajectory=list(self.telemetry.in_memory_exporter.get_finished_spans()),
            name=case.id,
        )
        evaluator = self.accuracy if case.category == ACCURACY else self.insufficient
        output = evaluator.evaluate(data)[0]
        groundedness = None
        if case.category == ACCURACY:
            groundedness = groundedness_result(self.groundedness.evaluate(data))
        return self._result(
            case,
            turn.answer,
            turn.agents,
            output.score,
            output.reason or "",
            sources=turn.sources,
            groundedness=groundedness,
            blocked=turn.blocked,
        )

    @staticmethod
    def _result(
        case: EvalCase,
        answer: str,
        agents: list[str],
        score: float,
        reason: str,
        sources: list | None = None,
        groundedness: dict | None = None,
        blocked: bool = False,
    ) -> dict:
        return {
            "caseId": case.id,
            "category": case.category,
            "expectedAgent": case.agent,
            "agents": agents,
            "technique": case.technique,
            "question": case.question,
            "expected": case.expected,
            "answer": answer[:4000],
            "score": score,
            "reason": reason[:2000],
            "groundedness": groundedness,
            "sources": (sources or [])[:10],
            "blocked": blocked,
            "passed": case_passed(case.category, score, groundedness),
        }


def main() -> int:
    evaluation_id = os.environ["EVALUATION_ID"]
    store = EvaluationStore(evaluation_id)
    cases = load_cases()
    store.update(startedAt=_now(), progress={"completed": 0, "total": len(cases)})

    settings = AgentSettings.load()
    evaluator = Evaluator(settings)
    results: list[dict] = []
    with gateway_client(settings) as mcp:
        tools = list_all_tools(mcp)
        for index, case in enumerate(cases, start=1):
            logger.info("Evaluando caso %s (%s/%s)", case.id, index, len(cases))
            results.append(evaluator.run_case(case, tools))
            store.update(progress={"completed": index, "total": len(cases)}, results=results)

    store.update(status="COMPLETED", finishedAt=_now(), summary=summarize(results), results=results)
    logger.info("Evaluación %s completada", evaluation_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
