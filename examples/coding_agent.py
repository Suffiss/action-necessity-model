"""A scripted coding agent fixing a README typo, with the necessity gate in its loop.

Run:  python examples/coding_agent.py

The "agent" proposes a fixed plan that contains typical waste (a re-read, an
unrelated file, a repo-wide search, a test run after a docs-only change).
Tools are in-memory fakes, so nothing touches your disk or network.
"""

from __future__ import annotations

from typing import Any

from suffiss.necessity import Decision, evaluate_action

files = {"README.md": "# Suffiss\nA gate for unnecesary agent actions.\n", "package.json": '{"name": "suffiss"}'}


def run_tool(action: dict[str, Any]) -> str:
    args = action["arguments"]
    if action["tool"] == "read_file":
        return files[args["path"]]
    if action["tool"] == "edit_file":
        files[args["path"]] = files[args["path"]].replace(args["old"], args["new"])
        return "ok"
    if action["tool"] == "grep":
        return "\n".join(f"{path}: match" for path, text in files.items() if args["query"] in text)
    if action["tool"] == "run_shell":
        return "120 passed\nexit_code=0"
    return "done"


def act(tool: str, description: str, **arguments: Any) -> dict[str, Any]:
    return {"type": tool, "tool": tool, "description": description, "arguments": arguments}


PLAN = [
    act("read_file", "Read README.md", path="README.md"),
    act("read_file", "Read README.md", path="README.md"),
    act("grep", "Search the entire repository for the typo", query="unnecesary", path="."),
    act("read_file", "Read package.json", path="package.json"),
    act("edit_file", "Fix the typo in README", path="README.md", old="unnecesary", new="unnecessary"),
    act("read_file", "Read README.md", path="README.md"),
    act("run_shell", "Run backend tests", command="pytest backend/"),
    act("finish", "Report the fix to the user"),
]


def main() -> None:
    goal = "Fix typo in README"
    history: list[dict[str, Any]] = []
    for action in PLAN:
        decision = evaluate_action({"goal": goal, "history": history, "proposed_action": action})
        # Policy: only skip what the gate is confident about; uncertain actions run.
        run = decision.decision is not Decision.UNNECESSARY
        if run:
            history.append({"action": action, "result": run_tool(action)})
        verdict = "run " if run else "skip"
        print(f"[{verdict}] {decision.decision.value:<11} {decision.reason_code.value:<24} {action['description']}")
    print(f"\nExecuted {len(history)} of {len(PLAN)} proposed actions.")


if __name__ == "__main__":
    main()
