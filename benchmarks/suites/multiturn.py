"""Multi-turn suite — measures performance across a conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


@register
class MultiTurnSuite(BenchmarkSuite):
    name = "multiturn"
    description = "Multi-turn conversation — measures per-turn performance degradation"

    conversation = [
        ("Turn 1", "I'm planning a trip to Japan. What are the top 3 cities to visit?"),
        ("Turn 2", "Tell me more about the second city you mentioned. What should I see there?"),
        ("Turn 3", "What's the best time of year to visit that city?"),
        ("Turn 4", "How should I get around? Is public transit good there?"),
        ("Turn 5", "What local foods should I try?"),
        ("Turn 6", "Can you suggest a 3-day itinerary for that city?"),
        ("Turn 7", "What about budget? How much should I expect to spend per day?"),
        ("Turn 8", "Any cultural etiquette I should know about?"),
    ]

    async def run(self, client: AppClient, context_length: int, config: dict, on_case_done=None) -> SuiteResult:
        cases: list[CaseResult] = []
        runs_per_case = config.get("runs_per_case") or self.default_runs

        for run_idx in range(runs_per_case):
            if run_idx > 0:
                await client.send_command("/clear")

            for i, (name, prompt) in enumerate(self.conversation):
                result = await client.send_prompt(prompt)

                if run_idx == 0:
                    cases.append(CaseResult(
                        name=name, prompt=prompt, metrics={},
                        runs=[RunResult(passed=True, metrics=result.metrics, details={})],
                        details={},
                    ))
                    if on_case_done:
                        on_case_done(cases[-1])
                else:
                    cases[i].runs.append(RunResult(
                        passed=True, metrics=result.metrics, details={},
                    ))
                    if on_case_done:
                        on_case_done(cases[-1])

        for case in cases:
            case.metrics = self._average_run_metrics(case.runs)

        metrics: dict = {}
        for case in cases:
            tok_s = case.metrics.get("tok_s")
            if tok_s is not None:
                metrics[f"{case.name}_tok_s"] = round(tok_s, 1)

        return SuiteResult(suite_name=self.name, metrics=metrics, cases=cases)

    def _average_run_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        avg: dict = {}
        for key in ["tok_s", "ttft_ms", "total_tokens", "duration_s", "context_used"]:
            values = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if values:
                avg[key] = sum(values) / len(values)
        return avg
