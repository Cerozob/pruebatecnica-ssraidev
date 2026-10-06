"""Casos de evaluación y métricas (docs/evaluacion.md, ADR-033)."""

from dataclasses import dataclass

from evaluation.scoring import case_passed, groundedness_result, injection_score, load_cases, summarize


def test_cases_cover_the_four_required_evaluations_and_three_agents():
    cases = load_cases()
    assert len(cases) >= 5
    assert {c.category for c in cases} == {"accuracy", "insufficient_information", "prompt_injection"}
    accuracy_agents = {c.agent for c in cases if c.category == "accuracy"}
    assert accuracy_agents == {"conversational_agent", "cloud_recommender_agent", "modernization_agent"}
    assert len({c.id for c in cases}) == len(cases)


def test_injection_passes_only_with_the_blocked_message():
    assert injection_score(True, "Bloqueado.", "Bloqueado.")[0] == 1.0
    assert injection_score(True, "otra cosa", "Bloqueado.")[0] == 0.5
    assert injection_score(False, "HACKEADO", "Bloqueado.")[0] == 0.0


def result(category, passed, score, groundedness=None):
    return {"category": category, "passed": passed, "score": score, "groundedness": groundedness}


def test_summary_metrics():
    summary = summarize(
        [
            result("accuracy", True, 1.0, {"score": 1.0}),
            result("accuracy", False, 0.5, {"score": 0.5}),
            result("insufficient_information", True, 1.0),
            result("prompt_injection", True, 1.0),
            result("prompt_injection", False, 0.0),
        ]
    )
    assert summary["total"] == 5 and summary["passed"] == 3
    assert summary["accuracy"] == 0.5
    assert summary["accuracyScore"] == 0.75
    assert summary["groundedness"] == 0.75
    assert summary["insufficientInformation"] == 1.0
    assert summary["promptInjectionBlocked"] == 0.5


def test_summary_without_cases_of_a_category_is_null():
    assert summarize([])["accuracy"] is None


@dataclass
class Output:
    score: float
    reason: str


def test_groundedness_api_error_has_no_score():
    access_denied = "API error: An error occurred (AccessDeniedException) when calling the Evaluate operation"
    groundedness = groundedness_result([Output(0.0, access_denied)])
    assert groundedness == {"score": None, "reason": access_denied}


def test_groundedness_averages_scores():
    groundedness = groundedness_result([Output(1.0, "bien"), Output(0.5, "parcial")])
    assert groundedness == {"score": 0.75, "reason": "bien | parcial"}


def test_groundedness_error_does_not_fail_an_accurate_answer():
    assert case_passed("accuracy", 1.0, {"score": None, "reason": "API error: ..."})
    assert not case_passed("accuracy", 1.0, {"score": 0.0, "reason": "No cita fuentes."})
    assert not case_passed("accuracy", 0.0, {"score": None, "reason": "API error: ..."})


def test_summary_ignores_groundedness_errors():
    summary = summarize([result("accuracy", True, 1.0, {"score": 1.0}), result("accuracy", True, 1.0, {"score": None})])
    assert summary["groundedness"] == 1.0
