"""Command-line interface: ``suffiss-necessity evaluate | benchmark | simulate``.

``benchmark`` and ``simulate`` use the dataset and runners that live in the
repository (``benchmarks/`` and ``simulations/``), so run them from a checkout.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Sequence, TextIO

from suffiss.necessity.evaluator import Evaluator, EvaluatorConfig
from suffiss.necessity.models import ActionDecision, ContextValidationError
from suffiss.necessity.scoring import Thresholds

EXIT_OK = 0
EXIT_USAGE = 2


def _read_context(source: str) -> object:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    return json.loads(text)


def _format_decision(decision: ActionDecision) -> str:
    lines = [
        f"Decision: {decision.decision.value.upper()}",
        f"Confidence: {decision.confidence:.2f}",
        f"Reason: {decision.reason_code.value}",
        f"Explanation: {decision.explanation}",
        "Signals:",
    ]
    lines += [f"  {name}: {value:.2f}" for name, value in decision.signals.to_dict().items()]
    return "\n".join(lines)


def _evaluate(args: argparse.Namespace, out: TextIO) -> int:
    thresholds = Thresholds(necessary=args.necessary, unnecessary=args.unnecessary)
    decision = Evaluator(EvaluatorConfig(thresholds=thresholds)).evaluate(_read_context(args.input))
    out.write((json.dumps(decision.to_dict(), indent=2) if args.json else _format_decision(decision)) + "\n")
    return EXIT_OK


def _repo_module(name: str) -> ModuleType:
    """Import a repository-level runner, falling back to the working directory."""
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        sys.path.insert(0, str(Path.cwd()))
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError as error:
            raise SystemExit(f"error: cannot import {name}; run this command from the repository root") from error


def _benchmark(args: argparse.Namespace, out: TextIO) -> int:
    runner = _repo_module("benchmarks.runner")
    path = Path(args.dataset) if args.dataset else runner.DEFAULT_DATASET
    out.write(runner.format_report(runner.run_cases(runner.load_cases(path))) + "\n")
    return EXIT_OK


def _simulate(args: argparse.Namespace, out: TextIO) -> int:
    runner = _repo_module("simulations.runner")
    path = Path(args.trajectories) if args.trajectories else runner.DEFAULT_TRAJECTORIES
    trajectories = runner.load_trajectories(path)
    evaluator = Evaluator()
    for policy in runner.POLICIES:
        results = [runner.simulate(t, evaluator, policy) for t in trajectories]
        out.write(runner.format_results(results, policy) + "\n")
        if args.steps:
            out.write("\n" + runner.format_step_log(results) + "\n")
        out.write("\n")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="suffiss-necessity", description="Judge whether an agent's next action is necessary.")
    commands = parser.add_subparsers(dest="command", required=True)

    evaluate = commands.add_parser("evaluate", help="evaluate one action context (JSON file, or - for stdin)")
    evaluate.add_argument("input")
    evaluate.add_argument("--json", action="store_true", help="print the full decision as JSON")
    evaluate.add_argument("--necessary", type=float, default=Thresholds.necessary, help="threshold for 'necessary'")
    evaluate.add_argument("--unnecessary", type=float, default=Thresholds.unnecessary, help="threshold for 'unnecessary'")
    evaluate.set_defaults(handler=_evaluate)

    benchmark = commands.add_parser("benchmark", help="run the labelled benchmark (from the repository root)")
    benchmark.add_argument("dataset", nargs="?", help="JSONL dataset (default: benchmarks/dataset.jsonl)")
    benchmark.set_defaults(handler=_benchmark)

    simulate = commands.add_parser("simulate", help="replay agent trajectories (from the repository root)")
    simulate.add_argument("trajectories", nargs="?", help="JSONL trajectories (default: simulations/trajectories.jsonl)")
    simulate.add_argument("--steps", action="store_true", help="print the per-step decision log")
    simulate.set_defaults(handler=_simulate)
    return parser


def main(argv: Sequence[str] | None = None, out: TextIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args, out or sys.stdout)
    except (OSError, json.JSONDecodeError, ContextValidationError, ValueError) as error:
        # Bad input is a usage problem: report it plainly instead of a traceback.
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
