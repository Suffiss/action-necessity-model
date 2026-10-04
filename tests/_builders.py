"""Small builders that keep test scenarios readable."""

from __future__ import annotations

from typing import Any, Iterable

from suffiss.necessity.evaluator import evaluate_action
from suffiss.necessity.models import ActionDecision


def act(type_: str, tool: str = "", description: str = "", **arguments: Any) -> dict[str, Any]:
    return {"type": type_, "tool": tool, "description": description, "arguments": arguments}


def rec(action: dict[str, Any], result: str = "") -> dict[str, Any]:
    return {"action": action, "result": result}


def judge(
    goal: str,
    proposed: dict[str, Any],
    history: Iterable[dict[str, Any]] = (),
    state: str = "",
) -> ActionDecision:
    return evaluate_action(
        {"goal": goal, "current_state": state, "history": list(history), "proposed_action": proposed}
    )


def read(path: str) -> dict[str, Any]:
    return act("file_read", "read_file", f"Read {path}", path=path)


def edit(path: str, description: str = "") -> dict[str, Any]:
    return act("file_edit", "edit_file", description or f"Edit {path}", path=path)


def run_tests(command: str = "pytest") -> dict[str, Any]:
    return act("command", "run_shell", "Run unit tests", command=command)
