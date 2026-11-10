import json

import pytest
from _builders import act, edit, read, rec, run_tests

from suffiss.necessity import Evaluator, EvaluatorConfig, evaluate_action, explain_action
from suffiss.necessity.adapters import AdapterAssessment
from suffiss.necessity.models import ActionContext, ReasonCode

SCENARIOS = {
    "duplicate read": {"goal": "Fix typo in README", "history": [rec(read("README.md"), "# Projcet")], "proposed_action": read("README.md")},
    "rerun after edit": {
        "goal": "Fix the failing date parser test",
        "history": [rec(run_tests(), "1 failed\nexit_code=1"), rec(edit("src/dates.py"), "ok")],
        "proposed_action": run_tests(),
    },
    "broad scan": {"goal": "Fix button padding", "proposed_action": act("index", "index_repository", "Index the entire repository", path=".")},
    "vague": {"goal": "help", "proposed_action": read("a.py")},
}


@pytest.mark.parametrize("name", SCENARIOS)
def test_explanation_agrees_with_evaluate(name: str) -> None:
    context = SCENARIOS[name]
    assert explain_action(context).decision == evaluate_action(context)


@pytest.mark.parametrize("name", SCENARIOS)
def test_contributions_add_up_to_the_rule_score(name: str) -> None:
    explanation = explain_action(SCENARIOS[name])
    expected = min(1.0, max(0.0, 0.5 + sum(c.value for c in explanation.contributions)))
    assert explanation.rule_score == pytest.approx(expected)
    assert explanation.score == pytest.approx(explanation.rule_score)  # no adapter configured


def test_contributions_are_ordered_by_weight() -> None:
    magnitudes = [abs(c.value) for c in explain_action(SCENARIOS["rerun after edit"]).contributions]
    assert magnitudes == sorted(magnitudes, reverse=True)


def test_facts_name_the_duplicated_history_step() -> None:
    facts = explain_action(SCENARIOS["duplicate read"]).facts
    assert facts["matching_history_step"] == {"step": 1, "result": "success", "changed_since": False, "repeats_since_change": 1}
    assert facts["action_kind"] == "read" and facts["changes_state"] is False


def test_facts_report_a_state_change_since_the_repeat() -> None:
    explanation = explain_action(SCENARIOS["rerun after edit"])
    assert explanation.facts["matching_history_step"]["changed_since"] is True
    assert explanation.contributions[0].reason is ReasonCode.STATE_CHANGED


def test_explanation_serializes_to_json() -> None:
    payload = explain_action(SCENARIOS["broad scan"]).to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert {"rule_score", "score", "contributions", "facts"} <= set(payload)
    assert payload["contributions"][0] == {"reason_code": "SCOPE_TOO_BROAD", "value": -0.4}


def test_adapter_blend_is_visible_in_the_explanation() -> None:
    class Agrees:
        name = "stub"

        def assess(self, context: ActionContext) -> AdapterAssessment:
            return AdapterAssessment(necessity=1.0, weight=0.5)

    explanation = Evaluator(EvaluatorConfig(adapter=Agrees())).explain(SCENARIOS["duplicate read"])
    assert explanation.score == pytest.approx(0.5 * explanation.rule_score + 0.5)
