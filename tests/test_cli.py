import io
import json
from pathlib import Path

import pytest

from suffiss.necessity.cli import EXIT_OK, EXIT_USAGE, main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "duplicate_read.json"


def run(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    return main(list(argv), out), out.getvalue()


def test_evaluate_prints_human_readable_decision() -> None:
    code, output = run("evaluate", str(EXAMPLE))
    assert code == EXIT_OK
    assert "Decision: UNNECESSARY" in output
    assert "Reason: DUPLICATE_ACTION" in output


def test_evaluate_json_output_matches_public_schema() -> None:
    code, output = run("evaluate", str(EXAMPLE), "--json")
    payload = json.loads(output)
    assert code == EXIT_OK
    assert set(payload) == {"decision", "confidence", "reason_code", "explanation", "signals"}


def test_evaluate_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.stdin", io.StringIO(EXAMPLE.read_text(encoding="utf-8")))
    code, output = run("evaluate", "-")
    assert code == EXIT_OK and "Decision:" in output


def test_evaluate_respects_threshold_flags() -> None:
    _, output = run("evaluate", str(EXAMPLE), "--unnecessary", "0.0", "--necessary", "1.0")
    assert "Decision: UNCERTAIN" in output


@pytest.mark.parametrize(
    "content",
    ["not json", '{"goal": "x"}', '{"goal": "x", "proposed_action": {"type": 1}}'],
)
def test_bad_input_exits_with_usage_error(tmp_path: Path, content: str, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "bad.json"
    path.write_text(content, encoding="utf-8")
    code, _ = run("evaluate", str(path))
    assert code == EXIT_USAGE
    assert capsys.readouterr().err.startswith("error:")


def test_missing_file_exits_with_usage_error() -> None:
    code, _ = run("evaluate", "does-not-exist.json")
    assert code == EXIT_USAGE


def test_invalid_thresholds_exit_with_usage_error() -> None:
    code, _ = run("evaluate", str(EXAMPLE), "--necessary", "0.2", "--unnecessary", "0.8")
    assert code == EXIT_USAGE


def test_benchmark_command_reports_metrics() -> None:
    code, output = run("benchmark")
    assert code == EXIT_OK
    assert "False unnecessary rate" in output


def test_simulate_command_reports_both_policies() -> None:
    code, output = run("simulate")
    assert code == EXIT_OK
    assert "Uncertain policy: execute" in output and "Uncertain policy: skip" in output
