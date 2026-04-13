"""Agent suite — tool use efficiency and accuracy across 9 test cases."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient

# Test case working directories are created here (relative to project root)
TEST_PROGRAMS_DIR = Path(__file__).resolve().parent.parent.parent / "test-programs"


def _make_work_dir(case_name: str, run_index: int) -> Path:
    """Create a clean working directory for a test case run."""
    import shutil
    safe_name = case_name.lower().replace(" ", "-").replace(",", "")
    if run_index > 0:
        dir_name = f"{safe_name}-run{run_index + 1}"
    else:
        dir_name = safe_name
    work_dir = TEST_PROGRAMS_DIR / dir_name
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)
    return work_dir


def base_setup(work_dir: Path) -> None:
    """Write permissive permissions file to the working directory."""
    permissions = {
        "read_file": "allow",
        "list_directory": "allow",
        "search_files": "allow",
        "write_file": "allow",
        "run_command": "allow",
        "allow_rules": [],
    }
    (work_dir / ".local-chat-llm-permissions").write_text(json.dumps(permissions))


def _run_python(work_dir: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a python command in the work dir, capturing output."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )


# ---- Case 1: Read and answer ----

def _case1_setup(work_dir: Path) -> None:
    (work_dir / "info.txt").write_text(
        "Title: My Project\nAuthor: Alice Chen\nVersion: 1.0\n"
    )

def _case1_verify(work_dir: Path, response: str) -> bool:
    return "Alice Chen" in response


# ---- Case 2: Create a file ----

def _case2_setup(work_dir: Path) -> None:
    pass

def _case2_verify(work_dir: Path, response: str) -> bool:
    f = work_dir / "greeting.txt"
    if not f.exists():
        return False
    return f.read_text().strip() == "Hello, World!"


# ---- Case 3: List and count ----

def _case3_setup(work_dir: Path) -> None:
    src = work_dir / "src"
    src.mkdir()
    for name in ["a.py", "b.py", "c.py", "d.py", "e.py"]:
        (src / name).write_text(f"# {name}\n")
    for name in ["data.txt", "notes.txt", "readme.txt"]:
        (src / name).write_text(f"{name}\n")

def _case3_verify(work_dir: Path, response: str) -> bool:
    return "5" in response


# ---- Case 4: Search and report ----

def _case4_setup(work_dir: Path) -> None:
    (work_dir / "app.py").write_text("# TODO: add logging\ndef main():\n    pass\n")
    (work_dir / "utils.py").write_text("# TODO: handle edge case\ndef helper():\n    pass\n")
    (work_dir / "config.py").write_text('todo_message = "TODO items go here"\n')
    (work_dir / "readme.md").write_text("# My Project\n\nA simple project.\n")

def _case4_verify(work_dir: Path, response: str) -> bool:
    has_app = "app.py" in response
    has_utils = "utils.py" in response
    no_readme_false_positive = "readme.md" not in response or "no TODO" in response.lower()
    return has_app and has_utils and no_readme_false_positive


# ---- Case 5: Read, modify, write ----

def _case5_setup(work_dir: Path) -> None:
    data = {"host": "localhost", "port": 3000, "debug": True}
    (work_dir / "config.json").write_text(json.dumps(data, indent=2))

def _case5_verify(work_dir: Path, response: str) -> bool:
    f = work_dir / "config.json"
    if not f.exists():
        return False
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError:
        return False
    return data.get("port") == 8080 and data.get("host") == "localhost" and data.get("debug") is True


# ---- Case 6: Multi-file creation ----

def _case6_setup(work_dir: Path) -> None:
    pass

def _case6_verify(work_dir: Path, response: str) -> bool:
    init = work_dir / "mathutils" / "__init__.py"
    ops = work_dir / "mathutils" / "operations.py"
    if not init.exists() or not ops.exists():
        return False
    result = _run_python(
        work_dir, "-c",
        "from mathutils.operations import add, multiply; "
        "assert add(2, 3) == 5; assert multiply(2, 3) == 6; print('OK')"
    )
    return result.returncode == 0


# ---- Case 7: Debug a broken script ----

def _case7_setup(work_dir: Path) -> None:
    (work_dir / "app.py").write_text(
        "def calculate(items):\n"
        "    factor = 1.1\n"
        "    total = 0\n"
        "    for item in items:\n"
        "        total += item * multiplier  # Bug: should be 'factor'\n"
        "    return total\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    result = calculate([10, 20, 30])\n"
        "    print(f'Total: {result}')\n"
    )

def _case7_verify(work_dir: Path, response: str) -> bool:
    result = _run_python(work_dir, "app.py")
    return result.returncode == 0 and "Total:" in result.stdout


# ---- Case 8: Create project with tests ----

def _case8_setup(work_dir: Path) -> None:
    pass

def _case8_verify(work_dir: Path, response: str) -> bool:
    if not (work_dir / "stringutils.py").exists():
        return False
    if not (work_dir / "test_stringutils.py").exists():
        return False
    test_content = (work_dir / "test_stringutils.py").read_text()
    test_count = test_content.count("def test_")
    if test_count < 3:
        return False
    result = _run_python(work_dir, "-m", "pytest", "test_stringutils.py", "-v")
    return result.returncode == 0


# ---- Case 9: Refactor across files ----

def _case9_setup(work_dir: Path) -> None:
    calc_func = (
        "def calculate_total(items):\n"
        "    return sum(item['price'] * item['qty'] for item in items)\n"
    )
    orders_code = (
        f"{calc_func}\n"
        "def main():\n"
        "    items = [{'price': 10, 'qty': 2}, {'price': 5, 'qty': 3}]\n"
        "    print(calculate_total(items))\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    invoices_code = (
        f"{calc_func}\n"
        "def main():\n"
        "    items = [{'price': 100, 'qty': 1}, {'price': 50, 'qty': 2}]\n"
        "    print(calculate_total(items))\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    (work_dir / "orders.py").write_text(orders_code)
    (work_dir / "invoices.py").write_text(invoices_code)

def _case9_verify(work_dir: Path, response: str) -> bool:
    utils = work_dir / "utils.py"
    orders = work_dir / "orders.py"
    invoices = work_dir / "invoices.py"
    if not utils.exists():
        return False
    if "calculate_total" not in utils.read_text():
        return False
    orders_text = orders.read_text()
    invoices_text = invoices.read_text()
    if "def calculate_total" in orders_text or "def calculate_total" in invoices_text:
        return False
    if "from utils import" not in orders_text or "from utils import" not in invoices_text:
        return False
    r1 = _run_python(work_dir, "orders.py")
    r2 = _run_python(work_dir, "invoices.py")
    return r1.returncode == 0 and r2.returncode == 0


# ---- Case registry ----

AGENT_CASES = [
    {"name": "Read and answer", "level": 1, "task": "Read the file `info.txt` and tell me what the author's name is.", "setup": _case1_setup, "verify": _case1_verify},
    {"name": "Create a file", "level": 1, "task": "Create a file called `greeting.txt` that contains exactly the text 'Hello, World!'", "setup": _case2_setup, "verify": _case2_verify},
    {"name": "List and count", "level": 2, "task": "How many Python files are in the `src/` directory?", "setup": _case3_setup, "verify": _case3_verify},
    {"name": "Search and report", "level": 2, "task": "Find all TODO comments in this project and list them with their file paths.", "setup": _case4_setup, "verify": _case4_verify},
    {"name": "Read, modify, write", "level": 3, "task": "The file `config.json` has the port set to 3000. Change it to 8080.", "setup": _case5_setup, "verify": _case5_verify},
    {"name": "Multi-file creation", "level": 3, "task": "Create a Python package called `mathutils` with an `__init__.py` that imports from `operations.py`. `operations.py` should have functions `add(a, b)` and `multiply(a, b)` that return their results.", "setup": _case6_setup, "verify": _case6_verify},
    {"name": "Debug a broken script", "level": 3, "task": "The script `app.py` has a bug. Fix it so it runs without errors.", "setup": _case7_setup, "verify": _case7_verify},
    {"name": "Create project with tests", "level": 4, "task": "Create a Python module `stringutils.py` with functions `reverse(s)`, `is_palindrome(s)`, and `word_count(s)`. Then create `test_stringutils.py` with pytest tests for each function. Run the tests and make sure they pass.", "setup": _case8_setup, "verify": _case8_verify},
    {"name": "Refactor across files", "level": 4, "task": "The function `calculate_total` is duplicated in both `orders.py` and `invoices.py`. Extract it into a shared `utils.py` module, update both files to import from there, and verify nothing is broken.", "setup": _case9_setup, "verify": _case9_verify},
]


@register
class AgentSuite(BenchmarkSuite):
    name = "agent"
    description = "Agent tool use — 9 cases across levels 1-4"

    async def run(self, client: AppClient, context_length: int, config: dict) -> SuiteResult:
        cases: list[CaseResult] = []
        runs_per_case = config.get("runs_per_case", 1)
        levels = config.get("levels")

        for case_def in AGENT_CASES:
            if levels and case_def["level"] not in levels:
                continue
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
        avg_iters_vals = [c.metrics.get("avg_iterations") for c in cases if c.metrics.get("avg_iterations") is not None]
        avg_tools_vals = [c.metrics.get("avg_tool_calls") for c in cases if c.metrics.get("avg_tool_calls") is not None]
        metrics: dict = {
            "reliable_pass_rate": round(reliable, 2),
            "any_pass_rate": round(any_pass, 2),
        }
        if avg_iters_vals:
            metrics["avg_iterations"] = round(sum(avg_iters_vals) / len(avg_iters_vals), 1)
        if avg_tools_vals:
            metrics["avg_tool_calls"] = round(sum(avg_tools_vals) / len(avg_tools_vals), 1)
        return metrics
