from _builders import act, judge, rec, run_tests

from suffiss.necessity.models import Decision, ReasonCode

PASSED = "===== 42 passed in 1.20s =====\nexit_code=0"


def test_repeated_test_run_without_code_change_is_unnecessary() -> None:
    decision = judge("Run unit tests", run_tests(), history=[rec(run_tests(), PASSED)])
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code in {
        ReasonCode.DUPLICATE_ACTION,
        ReasonCode.GOAL_ALREADY_COMPLETED,
        ReasonCode.UNCHANGED_RETRY,
    }


def test_extra_work_after_goal_completed_is_unnecessary() -> None:
    lint = act("command", "run_shell", "Run flake8 linter", command="flake8 .")
    decision = judge("Run unit tests", lint, history=[rec(run_tests(), PASSED)])
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.GOAL_ALREADY_COMPLETED
    assert decision.signals.task_completion_probability > 0.7


def test_finishing_after_goal_completed_is_not_blocked() -> None:
    finish = act("finish", "finish", "Report that all tests pass")
    decision = judge("Run unit tests", finish, history=[rec(run_tests(), PASSED)])
    assert decision.decision is Decision.NECESSARY


def test_partial_completion_of_compound_goal_does_not_block_next_step() -> None:
    restart = act("command", "run_shell", "Restart the api server", command="systemctl restart api")
    decision = judge(
        "Update the config timeout and restart the api server",
        restart,
        history=[rec(act("file_edit", "edit_file", "Update timeout in config", path="config.yaml"), "ok")],
    )
    assert decision.decision is not Decision.UNNECESSARY
