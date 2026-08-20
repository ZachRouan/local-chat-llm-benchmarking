"""Code suite — code generation quality and speed measurement."""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


def extract_python_code(text: str) -> str:
    """Extract Python code from a response, handling fenced code blocks.

    Input is the model's raw content (bench mode preserves fences and line
    lengths). The LAST fenced block is the model's final answer when it
    emits multiple versions.
    """
    pattern = r"```(?:python)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    lines = text.strip().split("\n")
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("def ", "class ", "import ", "from ", "    ", "\t")) or in_code:
            code_lines.append(line)
            in_code = True
        elif in_code and stripped == "":
            code_lines.append(line)
        elif in_code:
            break
    return "\n".join(code_lines).strip() if code_lines else ""


@register
class CodeSuite(BenchmarkSuite):
    name = "code"
    description = "Code generation — syntax validity and speed"

    prompts = [
        ("Fibonacci", "Write a Python function called `fibonacci(n)` that returns the nth Fibonacci number. Only output the function, no explanation."),
        ("Palindrome check", "Write a Python function called `is_palindrome(s)` that returns True if the string is a palindrome, False otherwise. Only output the function, no explanation."),
        ("Longest common prefix", "Write a Python function called `longest_common_prefix(strs)` that takes a list of strings and returns their longest common prefix. Only output the function, no explanation."),
        ("FizzBuzz", "Write a Python function called `fizzbuzz(n)` that returns a list of strings for numbers 1 to n, where multiples of 3 are 'Fizz', multiples of 5 are 'Buzz', multiples of both are 'FizzBuzz', and others are the number as a string. Only output the function, no explanation."),
        ("Flatten nested list", "Write a Python function called `flatten(lst)` that takes an arbitrarily nested list and returns a flat list of all elements. Only output the function, no explanation."),
    ]

    default_runs = 3

    async def run(self, client: AppClient, context_length: int, config: dict, on_case_done=None) -> SuiteResult:
        cases: list[CaseResult] = []
        all_metrics: list[dict] = []
        runs_per_case = config.get("runs_per_case") or self.default_runs

        for name, prompt in self.prompts:
            runs: list[RunResult] = []
            for _ in range(runs_per_case):
                result = await client.send_prompt(prompt)
                code = extract_python_code(result.response_text)
                syntax_valid = self._validate_syntax(code)

                run_metrics = dict(result.metrics)
                run_metrics["syntax_valid"] = syntax_valid

                runs.append(RunResult(
                    passed=syntax_valid,
                    metrics=run_metrics,
                    details={"extracted_code": code},
                ))
                await client.send_command("/clear")

            avg_metrics = self._average_run_metrics(runs)
            all_metrics.append(avg_metrics)
            cases.append(CaseResult(
                name=name, prompt=prompt, metrics=avg_metrics, runs=runs, details={},
            ))
            if on_case_done:
                on_case_done(cases[-1])

        return SuiteResult(
            suite_name=self.name,
            metrics=self._aggregate(all_metrics),
            cases=cases,
        )

    def _validate_syntax(self, code: str) -> bool:
        if not code.strip():
            return False
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _average_run_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        avg: dict = {}
        for key in ["tok_s", "ttft_ms", "total_tokens", "duration_s"]:
            values = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if values:
                avg[key] = sum(values) / len(values)
        avg["syntax_valid_rate"] = sum(1 for r in runs if r.metrics.get("syntax_valid")) / len(runs)
        return avg

    def _aggregate(self, case_metrics: list[dict]) -> dict:
        def _avg(key: str) -> float | None:
            vals = [m.get(key) for m in case_metrics if m.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        result = {}
        avg_tok_s = _avg("tok_s")
        if avg_tok_s is not None:
            result["avg_tok_s"] = round(avg_tok_s, 1)
        parse_rate = _avg("syntax_valid_rate")
        if parse_rate is not None:
            result["parse_rate"] = round(parse_rate, 2)
        return result
