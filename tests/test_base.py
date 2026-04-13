from benchmarks.suites.base import RunResult, CaseResult, SuiteResult


def test_run_result_creation():
    r = RunResult(passed=True, metrics={"tok_s": 25.0}, details={})
    assert r.passed is True
    assert r.metrics["tok_s"] == 25.0


def test_case_result_creation():
    run = RunResult(passed=True, metrics={"tok_s": 25.0}, details={})
    c = CaseResult(
        name="test case",
        prompt="Hello",
        metrics={"avg_tok_s": 25.0},
        runs=[run],
        details={},
    )
    assert c.name == "test case"
    assert len(c.runs) == 1


def test_suite_result_creation():
    s = SuiteResult(suite_name="speed", metrics={"avg_tok_s": 25.0}, cases=[])
    assert s.suite_name == "speed"
    assert s.cases == []


def test_case_result_pass_rate():
    runs = [
        RunResult(passed=True, metrics={}, details={}),
        RunResult(passed=False, metrics={}, details={}),
        RunResult(passed=True, metrics={}, details={}),
    ]
    c = CaseResult(name="x", prompt="x", metrics={}, runs=runs, details={})
    assert c.pass_rate == 2 / 3


def test_case_result_pass_rate_empty():
    c = CaseResult(name="x", prompt="x", metrics={}, runs=[], details={})
    assert c.pass_rate == 0.0
