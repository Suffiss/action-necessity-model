"""A tool-calling agent with a flaky API, gated by NecessityGate.

Run:  python examples/tool_agent.py

The gate keeps the history, runs uncertain retries (the safe default), caps
identical uncertain repeats, and reports how many calls it saved. The API is
an in-memory fake that times out once.
"""

from __future__ import annotations

from typing import Any

from suffiss.necessity import Action, GateConfig, NecessityGate

_responses = iter(["Error: request timed out", "22C, clear"])


def weather_api(action: Action) -> str:
    return next(_responses, "22C, clear")


def call(city: str) -> dict[str, Any]:
    return {"type": "api_call", "tool": "weather_api", "description": f"Get weather for {city}", "arguments": {"city": city}}


def main() -> None:
    gate = NecessityGate("Get the current weather in Tokyo", config=GateConfig(max_uncertain_repeats=2))
    for action in [call("Tokyo")] * 4:
        verdict, result = gate.run(action, execute=weather_api)
        if verdict.allow:
            print(f"[run ] {verdict.decision.decision.value:<11} {verdict.why:<24} -> {result}")
        else:
            print(f"[skip] {verdict.decision.decision.value:<11} {verdict.why}")
    stats = gate.stats
    print(f"\nSaved {stats.skipped} of {stats.proposed} calls ({stats.saved_ratio:.0%}).")


if __name__ == "__main__":
    main()
