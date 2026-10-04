# Action Necessity Model

A lightweight gate that helps AI agents avoid unnecessary actions before they happen.

> **Status:** early experiment (v0.0.1). Nothing here has been benchmarked yet.
> No performance numbers are claimed until they are measured.

## The question

> Given an AI agent's goal, current state, action history, and proposed next action,
> is that next action actually necessary?

The gate answers `necessary`, `unnecessary`, or `uncertain`, with a stable
machine-readable reason code. False blocking is treated as worse than allowing
some redundant work, so ambiguous cases resolve to `uncertain`.

## Suffiss

Suffiss is inspired by the idea of statistical sufficiency: keep what matters
for a good decision and remove what adds no useful value.

**Enough, but no more.**

## Principles

- Runs fully locally, at zero cost: deterministic rules, local heuristics, and
  simple string similarity. No API keys, no network calls, no telemetry.
- Interpretable: every decision exposes its signals and a reason code.
- Safety first: when unsure, do not block.

## Installation

```bash
pip install -e ".[dev]"
pytest
```

## Usage

_To be documented once the evaluator lands._

## License

Apache License 2.0. See [LICENSE](LICENSE).
