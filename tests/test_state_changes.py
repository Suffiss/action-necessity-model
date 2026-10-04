from _builders import act, edit, judge, read, rec, run_tests

from suffiss.necessity.models import Decision, ReasonCode


def test_rerunning_tests_after_code_change_is_necessary() -> None:
    decision = judge(
        "Fix the failing date parser test",
        run_tests(),
        history=[
            rec(run_tests(), "1 failed, 41 passed\nexit_code=1"),
            rec(edit("src/dates.py", "Fix off-by-one in parse_date"), "ok"),
        ],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.STATE_CHANGED


def test_rerunning_passed_tests_after_code_change_is_necessary() -> None:
    decision = judge(
        "Add input validation to the signup handler",
        run_tests(),
        history=[
            rec(run_tests(), "42 passed\nexit_code=0"),
            rec(edit("src/signup.py", "Validate email field"), "ok"),
        ],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.STATE_CHANGED


def test_retry_after_transient_failure_is_not_marked_necessary() -> None:
    call = act("api_call", "http_get", "Fetch service status", url="https://api.example.com/status")
    decision = judge(
        "Report the current service status",
        call,
        history=[rec(call, "Error: request timed out after 30s")],
    )
    assert decision.decision in {Decision.UNNECESSARY, Decision.UNCERTAIN}


def test_retry_after_deterministic_failure_with_unchanged_state_is_unnecessary() -> None:
    decision = judge(
        "Summarize the deployment notes",
        read("docs/deploy.md"),
        history=[rec(read("docs/deploy.md"), "Error: No such file or directory: docs/deploy.md")],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.UNCHANGED_RETRY


def test_retry_after_state_change_is_necessary() -> None:
    install = act("command", "run_shell", "Install dependencies", command="npm install")
    decision = judge(
        "Install project dependencies",
        install,
        history=[
            rec(install, "npm ERR! notarget No matching version for left-pad@9.9.9\nexit_code=1"),
            rec(edit("package.json", "Pin left-pad to 1.3.0"), "ok"),
        ],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.STATE_CHANGED


def test_verification_read_after_edit_is_useful() -> None:
    decision = judge(
        "Set debug to false in config.yaml",
        read("config.yaml"),
        history=[
            rec(read("config.yaml"), "debug: true\nport: 8080"),
            rec(edit("config.yaml", "Set debug: false"), "ok"),
        ],
    )
    assert decision.decision is not Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.VERIFICATION_REQUIRED


def test_second_verification_without_new_change_is_redundant() -> None:
    decision = judge(
        "Set debug to false in config.yaml",
        read("config.yaml"),
        history=[
            rec(read("config.yaml"), "debug: true\nport: 8080"),
            rec(edit("config.yaml", "Set debug: false"), "ok"),
            rec(read("config.yaml"), "debug: false\nport: 8080"),
        ],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.REDUNDANT_VERIFICATION


def test_failed_edit_does_not_count_as_state_change() -> None:
    decision = judge(
        "Set debug to false in config.yaml",
        read("config.yaml"),
        history=[
            rec(read("config.yaml"), "debug: true"),
            rec(edit("config.yaml"), "Error: permission denied"),
        ],
    )
    assert decision.decision is Decision.UNNECESSARY
