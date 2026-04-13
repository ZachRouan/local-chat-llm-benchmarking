#!/usr/bin/env python3
"""CLI entry point for the benchmarking system."""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from benchmarks.runner import AppClient, AppClientError
from benchmarks.results import save_results, load_results, find_previous_result, compute_deltas
from benchmarks.report import print_summary, print_delta_report
from benchmarks.suites import SUITE_REGISTRY

# Import all suites to trigger registration
import benchmarks.suites.speed
import benchmarks.suites.generation
import benchmarks.suites.code
import benchmarks.suites.context
import benchmarks.suites.multiturn
import benchmarks.suites.agent
import benchmarks.suites.e2e_project


RESULTS_DIR = Path(__file__).parent / "results"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark local-chat-llm performance and agent capabilities",
    )
    parser.add_argument("--server", help="Server host:port (e.g., localhost:8082)")
    parser.add_argument("--suite", help="Comma-separated suite names (default: all)")
    parser.add_argument("--compare", action="store_true", help="Compare against previous run")
    parser.add_argument("--list", action="store_true", help="List available suites")
    parser.add_argument("--results", help="Display results from a JSON file")
    parser.add_argument("--label", help="Tag this run with a label")
    parser.add_argument("--temperature", type=float, help="Override temperature")
    parser.add_argument("--max-tokens", type=int, help="Override max tokens")
    parser.add_argument("--runs", type=int, default=1, help="Runs per test case (default: 1)")
    return parser.parse_args()


def cmd_list() -> None:
    """List available benchmark suites."""
    print("Available suites:\n")
    for name, cls in sorted(SUITE_REGISTRY.items()):
        print(f"  {name:15s} {cls.description}")
    print()


def cmd_results(path: str) -> None:
    """Display results from a JSON file."""
    p = Path(path)
    if not p.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    data = load_results(p)
    print_summary(data)


async def cmd_run(args: argparse.Namespace) -> None:
    """Run benchmark suites."""
    if not args.server:
        print("Error: --server is required", file=sys.stderr)
        sys.exit(1)

    if args.suite:
        suite_names = [s.strip() for s in args.suite.split(",")]
        for name in suite_names:
            if name not in SUITE_REGISTRY:
                print(f"Error: Unknown suite '{name}'. Use --list to see available suites.", file=sys.stderr)
                sys.exit(1)
    else:
        suite_names = list(SUITE_REGISTRY.keys())

    env_overrides: dict[str, str] = {}
    if args.temperature is not None:
        env_overrides["LLAMA_TEMPERATURE"] = str(args.temperature)
    if args.max_tokens is not None:
        env_overrides["LLAMA_MAX_TOKENS"] = str(args.max_tokens)

    config = {"runs_per_case": args.runs}

    client = AppClient(
        server=args.server,
        env_overrides=env_overrides,
    )

    # Launch from a clean temp dir so non-agent suites can't touch real files
    scratch_dir = Path(tempfile.mkdtemp(prefix="bench-scratch-"))

    try:
        print(f"Starting local-chat-llm on {args.server}...")
        await client.start(cwd=scratch_dir)
        print(f"Connected. Model: {client.model or 'unknown'}, Context: {client.context_length or 'unknown'}")
        print()

        context_length = client.context_length or 4096
        suite_results: dict = {}

        for name in suite_names:
            suite_cls = SUITE_REGISTRY[name]
            suite = suite_cls()
            print(f"Running suite: {suite.name} — {suite.description}")
            result = await suite.run(client, context_length, config)

            suite_results[name] = {
                "metrics": result.metrics,
                "cases": [
                    {
                        "name": c.name,
                        "prompt": c.prompt,
                        "metrics": c.metrics,
                        "runs": [
                            {"passed": r.passed, "metrics": r.metrics, "details": r.details}
                            for r in c.runs
                        ],
                        **({"level": c.details["level"]} if "level" in c.details else {}),
                    }
                    for c in result.cases
                ],
            }

            await client.send_command("/clear")

        data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "model": client.model or "unknown",
            "server": args.server,
            "context_length": context_length,
            "label": args.label,
            "runs_per_case": args.runs,
            "suites": suite_results,
        }

        result_path = save_results(data, RESULTS_DIR)
        print_summary(data)
        print(f"Results saved to {result_path}")

        if args.compare:
            model = client.model or "unknown"
            prev_path = find_previous_result(model, RESULTS_DIR, exclude=result_path)
            if prev_path:
                prev_data = load_results(prev_path)
                deltas = compute_deltas(data, prev_data)
                current_label = args.label or "current"
                previous_label = prev_data.get("label") or prev_path.stem
                print_delta_report(deltas, current_label=current_label, previous_label=previous_label)
            else:
                print(f"\nNo previous results found for {model}. Nothing to compare.")

    except AppClientError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        await client.stop()
        shutil.rmtree(scratch_dir, ignore_errors=True)


def main() -> None:
    args = parse_args()

    if args.list:
        cmd_list()
        return

    if args.results:
        cmd_results(args.results)
        return

    if not args.server:
        print("Error: --server is required (or use --list / --results)", file=sys.stderr)
        sys.exit(1)

    asyncio.run(cmd_run(args))


if __name__ == "__main__":
    main()
