"""A tool-calling agent with a flaky API, showing how to handle ``uncertain``.

Run:  python examples/tool_agent.py

The gate does not decide retry budgets; it reports when a retry is unchanged.
This example's policy: run uncertain actions, but cap identical retries.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from suffiss.necessity import Decision, evaluate_action

MAX_UNCERTAIN_REPEATS = 2
_responses = iter(["Error: request timed out", "22C, clear"])


def weather_api(city: str) -> str:
    return next(_responses, "22C, clear")


def call(city: str) -> dict[str, Any]:
    return {"type": "api_call", "tool": "weather_api", "description": f"Get weather for {city}", "arguments": {"city": city}}


def main() -> None:
    goal = "Get the current weather in Tokyo"
    history: list[dict[str, Any]] = []
    attempts: Counter[str] = Counter()
    for action in [call("Tokyo")] * 4:
        decision = evaluate_action({"goal": goal, "history": history, "proposed_action": action})
        key = repr(sorted(action["arguments"].items()))
        over_budget = decision.decision is Decision.UNCERTAIN and attempts[key] >= MAX_UNCERTAIN_REPEATS
        if decision.decision is Decision.UNNECESSARY or over_budget:
            print(f"[skip] {decision.decision.value:<11} {decision.reason_code.value}")
            continue
        attempts[key] += 1
        result = weather_api(action["arguments"]["city"])
        history.append({"action": action, "result": result})
        print(f"[run ] {decision.decision.value:<11} {decision.reason_code.value:<24} -> {result}")


if __name__ == "__main__":
    main()
