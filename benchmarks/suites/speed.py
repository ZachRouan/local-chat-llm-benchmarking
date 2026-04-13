"""Speed suite — short Q&A throughput measurement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


@register
class SpeedSuite(BenchmarkSuite):
    name = "speed"
    description = "Short Q&A throughput — measures TTFT and tok/s"

    prompts = [
        ("Capital of France", "What is the capital of France?"),
        ("Hash table", "Explain what a hash table is in two sentences."),
        ("Photosynthesis", "What is photosynthesis? Answer in one paragraph."),
        ("Largest planet", "What is the largest planet in our solar system and why?"),
        ("HTTP status 404", "What does HTTP status code 404 mean?"),
        ("Binary search", "Explain binary search in three sentences."),
        ("Water boiling point", "At what temperature does water boil at sea level, in Celsius and Fahrenheit?"),
    ]

    async def run(self, client: AppClient, context_length: int, config: dict) -> SuiteResult:
        cases: list[CaseResult] = []
        all_metrics: list[dict] = []
        runs_per_case = config.get("runs_per_case", 1)

        for name, prompt in self.prompts:
            runs: list[RunResult] = []
            for _ in range(runs_per_case):
                result = await client.send_prompt(prompt)
                runs.append(RunResult(
                    passed=True,
                    metrics=result.metrics,
                    details={},
                ))
                await client.send_command("/clear")

            avg_metrics = self._average_run_metrics(runs)
            all_metrics.append(avg_metrics)
            cases.append(CaseResult(
                name=name, prompt=prompt, metrics=avg_metrics, runs=runs, details={},
            ))

        return SuiteResult(
            suite_name=self.name,
            metrics=self._aggregate(all_metrics),
            cases=cases,
        )

    def _average_run_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        keys = ["tok_s", "ttft_ms", "total_tokens", "duration_s"]
        avg: dict = {}
        for key in keys:
            values = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if values:
                avg[key] = sum(values) / len(values)
        return avg

    def _aggregate(self, case_metrics: list[dict]) -> dict:
        def _avg(key: str) -> float | None:
            vals = [m.get(key) for m in case_metrics if m.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        result = {}
        avg_tok_s = _avg("tok_s")
        if avg_tok_s is not None:
            result["avg_tok_s"] = round(avg_tok_s, 1)
        avg_ttft = _avg("ttft_ms")
        if avg_ttft is not None:
            result["avg_ttft_ms"] = round(avg_ttft, 1)
        return result
