"""Base classes and data types for benchmark suites."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from benchmarks.runner import AppClient

# Called after each case completes: on_case_done(case_result)
ProgressCallback = Callable[["CaseResult"], None] | None


@dataclass
class RunResult:
    """Result of a single run of a single test case."""
    passed: bool
    metrics: dict
    details: dict


@dataclass
class CaseResult:
    """Result of a test case across all runs."""
    name: str
    prompt: str
    metrics: dict
    runs: list[RunResult]
    details: dict

    @property
    def pass_rate(self) -> float:
        if not self.runs:
            return 0.0
        return sum(1 for r in self.runs if r.passed) / len(self.runs)


@dataclass
class SuiteResult:
    """Result of an entire benchmark suite."""
    suite_name: str
    metrics: dict
    cases: list[CaseResult]


class BenchmarkSuite:
    """Base class for all benchmark suites."""
    name: str = ""
    description: str = ""
    # Per-suite default when --runs is not passed; pass/fail suites override
    # with >1 so single-flip variance at nonzero temperature isn't read as
    # a real quality difference.
    default_runs: int = 1

    async def run(self, client: AppClient, context_length: int, config: dict, on_case_done: ProgressCallback = None) -> SuiteResult:
        raise NotImplementedError
