"""A scripted research agent that tends to repeat searches.

Run:  python examples/research_agent.py

The search engine is an in-memory dictionary. The gate skips the cosmetically
different repeat and lets the genuinely new query through. It also lets the
linked-article fetch through even though both answers are already known: the
gate cannot recognise "answer already in hand" (a documented limitation).
"""

from __future__ import annotations

from typing import Any

from suffiss.necessity import Decision, evaluate_action

INDEX = {
    "eiffel tower completion year": "The Eiffel Tower was completed in 1889. See en.wikipedia.org/wiki/Eiffel_Tower",
    "eiffel tower height": "The tower is 330 metres (1,083 ft) tall.",
}


def search(query: str) -> str:
    return INDEX.get(" ".join(query.lower().split()), "No results.")


def web_search(query: str) -> dict[str, Any]:
    return {"type": "search", "tool": "web_search", "description": f"Search for {query}", "arguments": {"query": query}}


PLAN = [
    web_search("Eiffel Tower completion year"),
    web_search("eiffel tower  completion year"),
    web_search("Eiffel Tower height"),
    {
        "type": "browse",
        "tool": "fetch_url",
        "description": "Open the linked article",
        "arguments": {"url": "https://en.wikipedia.org/wiki/Eiffel_Tower"},
    },
]


def main() -> None:
    goal = "Find the year the Eiffel Tower was completed and its height"
    history: list[dict[str, Any]] = []
    for action in PLAN:
        decision = evaluate_action({"goal": goal, "history": history, "proposed_action": action})
        if decision.decision is Decision.UNNECESSARY:
            print(f"[skip] {decision.reason_code.value:<24} {action['description']}")
            continue
        query = action["arguments"].get("query", "")
        result = search(query) if query else "(article text)"
        history.append({"action": action, "result": result})
        print(f"[run ] {decision.reason_code.value:<24} {action['description']} -> {result[:50]}")


if __name__ == "__main__":
    main()
