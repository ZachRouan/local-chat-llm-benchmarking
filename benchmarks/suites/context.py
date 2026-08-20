"""Context suite — measures performance degradation as context fills."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


_FILLER_BLOCK = (
    "The history of artificial intelligence began in antiquity, with myths and stories "
    "of artificial beings endowed with intelligence. The seeds of modern AI were planted "
    "by philosophers who attempted to describe the process of human thinking as the "
    "mechanical manipulation of symbols. This work culminated in the invention of the "
    "programmable digital computer in the 1940s, a machine based on the abstract essence "
    "of mathematical reasoning. This device and the ideas behind it inspired a handful of "
    "scientists to begin seriously discussing the possibility of building an electronic brain. "
)


@register
class ContextSuite(BenchmarkSuite):
    name = "context"
    description = "Context window scaling — measures tok/s degradation as context fills"

    fill_levels = [0.10, 0.25, 0.50, 0.75, 0.90]
    question = "In one sentence, what is the main topic of the text that follows?"
    # Reserve room for the response: prompt tokens + max_tokens must fit in ctx.
    _OUTPUT_RESERVE_TOKENS = 9000

    async def run(self, client: AppClient, context_length: int, config: dict, on_case_done=None) -> SuiteResult:
        cases: list[CaseResult] = []
        runs_per_case = config.get("runs_per_case") or self.default_runs

        for level in self.fill_levels:
            target_tokens = min(
                int(context_length * level),
                max(context_length - self._OUTPUT_RESERVE_TOKENS, 1024),
            )
            target_chars = target_tokens * 4
            filler = self._generate_filler(target_chars)
            # Single line: the app reads prompts with input(), so any newline
            # splits the prompt into separate turns. Level-specific prefix
            # defeats server prefix-cache reuse across fill levels.
            prompt = f"[fill test {int(level * 100)}] {self.question} {filler}".replace("\n", " ")
            name = f"{int(level * 100)}% fill"

            runs: list[RunResult] = []
            for _ in range(runs_per_case):
                result = await client.send_prompt(prompt)
                runs.append(RunResult(passed=True, metrics=result.metrics, details={}))
                await client.send_command("/clear")

            avg_metrics = self._average_run_metrics(runs)
            cases.append(CaseResult(
                name=name, prompt=f"[{name} context filler + question]",
                metrics=avg_metrics, runs=runs, details={},
            ))
            if on_case_done:
                on_case_done(cases[-1])

        metrics: dict = {}
        for case in cases:
            tok_s = case.metrics.get("tok_s")
            if tok_s is not None:
                metrics[f"{case.name}_tok_s"] = round(tok_s, 1)

        return SuiteResult(suite_name=self.name, metrics=metrics, cases=cases)

    def _generate_filler(self, target_chars: int) -> str:
        repeats = (target_chars // len(_FILLER_BLOCK)) + 1
        text = (_FILLER_BLOCK * repeats)[:target_chars]
        return text.strip()

    def _average_run_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        avg: dict = {}
        for key in ["tok_s", "ttft_ms", "total_tokens", "duration_s"]:
            values = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if values:
                avg[key] = sum(values) / len(values)
        return avg
