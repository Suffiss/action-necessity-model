"""Keep the README's quick start honest: its code must run and its output must match."""

import json
import re
from pathlib import Path

import pytest

README = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")


def _blocks(language: str) -> list[str]:
    return re.findall(rf"```{language}\n(.*?)```", README, flags=re.S)


def test_quick_start_runs_and_prints_documented_result(capsys: pytest.CaptureFixture[str]) -> None:
    namespace: dict[str, object] = {}
    exec(_blocks("python")[0], namespace)  # noqa: S102 - executing our own README snippet
    assert capsys.readouterr().out.strip() == "unnecessary DUPLICATE_ACTION"
    documented = json.loads(_blocks("json")[0])
    assert namespace["decision"].to_dict() == documented  # type: ignore[attr-defined]
