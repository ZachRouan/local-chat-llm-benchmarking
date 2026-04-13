"""Generation suite — long-form output throughput measurement."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


@register
class GenerationSuite(BenchmarkSuite):
    name = "generation"
    description = "Long-form generation — measures sustained tok/s"

    prompts = [
        ("History of computing", "Write a detailed essay about the history of computing, from early mechanical calculators to modern processors. Cover at least 5 major milestones."),
        ("Explain machine learning", "Write a comprehensive explanation of how machine learning works, covering supervised learning, unsupervised learning, and neural networks. Include examples for each."),
        ("Space exploration", "Write a detailed overview of humanity's space exploration achievements, from Sputnik to the James Webb Space Telescope. Discuss the significance of each milestone."),
    ]

    async def run(self, client: AppClient, context_length: int, config: dict, on_case_done=None) -> SuiteResult:
        cases: list[CaseResult] = []
        all_metrics: list[dict] = []
        runs_per_case = config.get("runs_per_case", 1)

        for name, prompt in self.prompts:
            runs: list[RunResult] = []
            for _ in range(runs_per_case):
                result = await client.send_prompt(prompt)
                runs.append(RunResult(
                    passed=True, metrics=result.metrics, details={},
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
        avg_duration = _avg("duration_s")
        if avg_duration is not None:
            result["avg_duration_s"] = round(avg_duration, 1)
        return result
