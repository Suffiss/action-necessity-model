# Action Necessity Model

A lightweight gate that helps AI agents avoid unnecessary actions before they happen.

[![tests](https://github.com/Suffiss/action-necessity-model/actions/workflows/tests.yml/badge.svg)](https://github.com/Suffiss/action-necessity-model/actions/workflows/tests.yml)
![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-Apache--2.0-green)

> **Status: research prototype (v0.0.1).** The numbers below come from small,
> hand-built benchmarks. They are evidence that the idea is worth pursuing,
> not proof that it works in production.

## The problem

AI agents often:

- reread files they already have
- repeat searches with cosmetically different wording
- retry operations that failed for reasons that have not changed
- keep calling tools after the task is complete
- inspect far more context than the task needs

Each wasted action costs tokens, tool fees and latency, and every extra call
widens the surface for failure.

## The question

> Given an agent's **goal**, **current state**, **action history** and
> **proposed next action**, is that next action actually necessary?

The gate answers `necessary`, `unnecessary` or `uncertain`, with a stable
machine-readable reason code, a confidence, and the signals behind it.

## Suffiss: enough, but no more

Suffiss is inspired by statistical sufficiency: keep what matters for a good
decision and remove what adds no useful value.

The objective is **not** to minimise actions at all costs. It is to keep task
success while removing redundant work. Wrongly blocking a necessary action is
treated as worse than allowing a redundant one, so anything ambiguous resolves
to `uncertain`.

```text
Without gate
  Agent → Tool → Tool → Tool → Tool

With gate
  Agent → Proposed action → Necessity Gate ─┬─ necessary   → execute
                                            ├─ unnecessary → skip
                                            └─ uncertain   → follow your policy (recommended: execute)
```

## Install

```bash
git clone https://github.com/Suffiss/action-necessity-model.git
cd action-necessity-model
pip install -e ".[dev]"
pytest
```

The package needs only Python 3.11+. It has no runtime dependencies, makes no
network calls, collects no telemetry, and needs no API keys.

## Quick start

```python
from suffiss.necessity import Decision, evaluate_action

decision = evaluate_action({
    "goal": "Fix typo in README",
    "current_state": "README has been read; no edits yet.",
    "history": [
        {
            "action": {"type": "file_read", "tool": "read_file",
                       "description": "Read README.md", "arguments": {"path": "README.md"}},
            "result": "# Suffiss\nA gate for unnecesary agent actions.",
        }
    ],
    "proposed_action": {"type": "file_read", "tool": "read_file",
                        "description": "Read README.md again", "arguments": {"path": "README.md"}},
})

print(decision.decision, decision.reason_code)   # unnecessary DUPLICATE_ACTION
if decision.decision is not Decision.UNNECESSARY:
    ...  # execute the action
```

`evaluate_action` accepts a plain dict or an `ActionContext` and returns an
`ActionDecision`:

```json
{
  "decision": "unnecessary",
  "confidence": 0.7857,
  "reason_code": "DUPLICATE_ACTION",
  "explanation": "An equivalent action already ran and nothing relevant changed since. (necessity score 0.15)",
  "signals": {
    "goal_relevance": 1.0,
    "new_information_gain": 0.0,
    "duplicate_action_probability": 1.0,
    "task_completion_probability": 0.0,
    "scope_alignment": 1.0
  }
}
```

Thresholds, weights, the similarity provider and an optional model adapter
are all set through `Evaluator(EvaluatorConfig(...))`.

Runnable agent loops live in [`examples/`](examples). They use in-memory fake
tools, so nothing touches your disk or network.

## CLI

```bash
suffiss-necessity evaluate examples/duplicate_read.json   # or "-" for stdin, --json for raw output
suffiss-necessity benchmark                               # from the repository root
suffiss-necessity simulate --steps                        # from the repository root
```

```text
Decision: UNNECESSARY
Confidence: 0.79
Reason: DUPLICATE_ACTION
```

## Reason codes

Reason codes are the primary output. The explanations are secondary.

| Supports executing | Supports skipping | Abstaining |
|---|---|---|
| `DIRECT_GOAL_DEPENDENCY` | `DUPLICATE_ACTION` | `INSUFFICIENT_CONTEXT` |
| `NEW_INFORMATION_REQUIRED` | `GOAL_ALREADY_COMPLETED` | |
| `PREREQUISITE_ACTION` | `SCOPE_TOO_BROAD` | |
| `STATE_CHANGED` | `REDUNDANT_VERIFICATION` | |
| `VERIFICATION_REQUIRED` | `UNCHANGED_RETRY` | |
| | `LOW_GOAL_RELEVANCE` | |
| | `NO_NEW_INFORMATION` (reserved, not emitted yet) | |

## How it works

Everything is deterministic: rules, light text heuristics and local string
similarity.

1. **Classify.** Each action is classified by kind (read, search, request,
   execute, write, finish) and by whether it changes state. Each result is
   classified as success, failure, transient failure or pending.
2. **Extract features.** These include:
   - duplicates with normalized arguments, and whether anything that affects
     the target changed since
   - verification of the agent's own change
   - prerequisites, and knowledge gaps stated in `current_state`
   - paging through truncated output and following leads from earlier results
   - goal completion, scope breadth, and goal relevance (by clause and by
     concept)
3. **Score.** Start at 0.5, add supporting contributions and subtract
   penalties. Each contribution carries its reason code. The defaults are
   `necessary` at 0.65 or above and `unnecessary` at 0.35 or below.
4. **Abstain** with `INSUFFICIENT_CONTEXT` when the goal or the action is too
   vague. A weak context never blocks an action.

See [docs/architecture.md](docs/architecture.md) for the full design and the
evaluation methodology.

## Measured results

All runs are recorded verbatim, including regressions, in
[benchmarks/RESULTS.md](benchmarks/RESULTS.md) and
[simulations/RESULTS.md](simulations/RESULTS.md).

**Single-decision benchmark.** Labels were committed before each evaluation.

| Set | Cases | Accuracy | False unnecessary | Unnecessary detected | Uncertain |
|---|---|---|---|---|---|
| Dev, first run | 30 | 0.77 | 0.0% | 78.6% | 23.3% |
| Dev, after fixes (in-sample) | 30 | 0.90 | 0.0% | 85.7% | 13.3% |
| Held-out (run once, never tuned on) | 12 | 0.83 | 0.0% | 100.0% | 8.3% |

**Trajectory simulation.** Six agent runs, 39 steps, 23 of them essential.

| Uncertain policy | Actions | Saved | Avoidable removed | Still successful |
|---|---|---|---|---|
| execute (recommended) | 39 → 27 | 30.8% | 12 of 16 | 6 of 6 |
| skip | 39 → 22 | 43.6% | 13 of 16 | 3 of 6 |

**How to read this:**

- **Sample sizes are tiny.** Only 17 truly-necessary cases exist across the
  two benchmark sets. Zero false blocks out of 17 still leaves a 95% upper
  bound of about 18% (rule of three). The research target of < 3% false
  blocking is **not** demonstrated.
- **The dev "after fixes" row is optimistic.** The fixes were motivated by
  failures on those same cases.
- **Skipping `uncertain` breaks half the trajectories.** Treat `uncertain` as
  "execute" unless you have your own budget logic (see
  [`examples/tool_agent.py`](examples/tool_agent.py)).

## Limitations

- Relevance is lexical: token overlap plus about 11 hand-written concept
  groups in [`lexicon.py`](src/suffiss/necessity/lexicon.py). Wording outside
  that vocabulary tends to come out `uncertain`.
- The gate cannot tell that an answer is already in hand. A reworded search
  for a fact the agent already found is still allowed.
- Goal completion is only inferred for single-clause goals such as "run …" or
  "fix …", or from explicit markers.
- The gate judges necessity, not safety or correctness. It is not a planner,
  a router, or a hallucination detector.

## Extension points

These are interfaces only. Nothing is implemented yet.

- `SimilarityProvider`: plug in embedding similarity.
- `NecessityAdapter`: blend a model's opinion (a local classifier, a
  fine-tuned small model, or a teacher model) into the rule score.

Agent-framework integrations (OpenAI Agents SDK, MCP, LangGraph, AutoGen,
CrewAI) need only a thin wrapper around `evaluate_action` and are deliberately
out of scope for v0.

## Project layout

```text
src/suffiss/necessity/   models, rules, features, scoring, similarity, evaluator, CLI
benchmarks/              labelled cases, held-out set, metrics, runner, results log
simulations/             labelled trajectories, simulator, results log
examples/                runnable gated agent loops
docs/architecture.md     design and evaluation methodology
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
