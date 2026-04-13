"""E2E project suite — full project creation test cases (level 5)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.agent import base_setup, _make_work_dir
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


def _run_python(work_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---- Case 10: CLI tool ----

def _case10_setup(work_dir: Path) -> None:
    pass

def _case10_verify(work_dir: Path, response: str) -> bool:
    taskman = work_dir / "taskman.py"
    if not taskman.exists():
        return False

    r = _run_python(work_dir, "taskman.py", "add", "Buy milk")
    if r.returncode != 0:
        return False
    r = _run_python(work_dir, "taskman.py", "add", "Write tests")
    if r.returncode != 0:
        return False

    r = _run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False
    if "Buy milk" not in r.stdout or "Write tests" not in r.stdout:
        return False

    r = _run_python(work_dir, "taskman.py", "done", "1")
    if r.returncode != 0:
        return False

    r = _run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False
    output_lower = r.stdout.lower()
    if "done" not in output_lower and "✓" not in r.stdout and "[x]" not in output_lower:
        return False

    r = _run_python(work_dir, "taskman.py", "clear")
    if r.returncode != 0:
        return False

    r = _run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False

    tasks_file = work_dir / "tasks.json"
    if tasks_file.exists():
        try:
            json.loads(tasks_file.read_text())
        except json.JSONDecodeError:
            return False

    test_file = work_dir / "test_taskman.py"
    if test_file.exists():
        r = _run_python(work_dir, "-m", "pytest", "test_taskman.py", "-v")
        if r.returncode != 0:
            return False

    return True


# ---- Case 11: Multi-module project ----

def _case11_setup(work_dir: Path) -> None:
    pass

def _case11_verify(work_dir: Path, response: str) -> bool:
    for name in ["shortener.py", "storage.py", "cli.py"]:
        if not (work_dir / name).exists():
            return False

    r = _run_python(work_dir, "cli.py", "shorten", "https://example.com")
    if r.returncode != 0:
        return False
    code = r.stdout.strip().split()[-1]
    if not code:
        return False

    r = _run_python(work_dir, "cli.py", "resolve", code)
    if r.returncode != 0:
        return False
    if "https://example.com" not in r.stdout:
        return False

    test_files = list(work_dir.glob("test_*.py"))
    if test_files:
        r = _run_python(work_dir, "-m", "pytest", "-v")
        if r.returncode != 0:
            return False

    return True


E2E_CASES = [
    {
        "name": "CLI tool",
        "level": 5,
        "task": (
            "Create a Python CLI tool called `taskman.py` that manages a TODO list "
            "stored in `tasks.json`. It should support these commands via argparse: "
            "`add <task>` (adds a task), `list` (shows all tasks with IDs), "
            "`done <id>` (marks a task as done), and `clear` (removes all tasks). "
            "Include `test_taskman.py` with tests and make sure they pass."
        ),
        "setup": _case10_setup,
        "verify": _case10_verify,
    },
    {
        "name": "Multi-module project",
        "level": 5,
        "task": (
            "Create a URL shortener with three modules: `shortener.py` (generates "
            "short codes from URLs using hashlib), `storage.py` (in-memory dict with "
            "`save(path)` and `load(path)` methods for JSON persistence), and `cli.py` "
            "(argparse CLI with `shorten <url>` and `resolve <code>` commands). "
            "Include tests and make sure they pass."
        ),
        "setup": _case11_setup,
        "verify": _case11_verify,
    },
]


@register
class E2EProjectSuite(BenchmarkSuite):
    name = "e2e_project"
    description = "End-to-end project creation — level 5 (expert)"

    async def run(self, client: AppClient, context_length: int, config: dict) -> SuiteResult:
        cases: list[CaseResult] = []
        runs_per_case = config.get("runs_per_case", 1)

        for case_def in E2E_CASES:
            runs: list[RunResult] = []

            for run_idx in range(runs_per_case):
                work_dir = _make_work_dir(case_def["name"], run_idx)
                base_setup(work_dir)
                case_def["setup"](work_dir)

                # Restart app from the test's working directory
                await client.stop()
                await client.start(cwd=work_dir)
                await client.send_command("/agent on")

                result = await client.send_prompt(case_def["task"])

                passed = case_def["verify"](work_dir, result.response_text)

                run_metrics = dict(result.metrics)
                self_verified = any(
                    entry.get("tool_name") == "run_command"
                    for entry in result.tool_log
                    if entry.get("type") == "call"
                )
                run_metrics["self_verified"] = self_verified

                runs.append(RunResult(
                    passed=passed,
                    metrics=run_metrics,
                    details={
                        "tool_log": result.tool_log,
                        "response_text": result.response_text,
                    },
                ))

            case_metrics = self._compute_case_metrics(runs)
            cases.append(CaseResult(
                name=case_def["name"],
                prompt=case_def["task"],
                metrics=case_metrics,
                runs=runs,
                details={"level": case_def["level"]},
            ))

        suite_metrics = self._compute_suite_metrics(cases)
        return SuiteResult(suite_name=self.name, metrics=suite_metrics, cases=cases)

    def _compute_case_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        metrics: dict = {}
        metrics["pass_rate"] = sum(1 for r in runs if r.passed) / len(runs)
        for key in ["iterations", "tool_calls", "tool_errors"]:
            vals = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if vals:
                metrics[f"avg_{key}"] = sum(vals) / len(vals)
        return metrics

    def _compute_suite_metrics(self, cases: list[CaseResult]) -> dict:
        if not cases:
            return {}
        total = len(cases)
        reliable = sum(1 for c in cases if c.pass_rate == 1.0) / total
        any_pass = sum(1 for c in cases if c.pass_rate > 0.0) / total
        return {
            "reliable_pass_rate": round(reliable, 2),
            "any_pass_rate": round(any_pass, 2),
        }
