from io import StringIO
from rich.console import Console
from benchmarks.report import print_summary, print_delta_report


def _capture(func, *args, **kwargs) -> str:
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    func(*args, console=console, **kwargs)
    return buf.getvalue()


def test_print_summary_speed():
    data = {
        "model": "test-model",
        "server": "localhost:8082",
        "label": "test run",
        "runs_per_case": 1,
        "suites": {
            "speed": {
                "metrics": {"avg_tok_s": 25.0, "avg_ttft_ms": 180.0},
                "cases": [],
            },
        },
    }
    output = _capture(print_summary, data)
    assert "test-model" in output
    assert "25.0" in output


def test_print_summary_agent_multirun():
    data = {
        "model": "test-model",
        "server": "localhost:8082",
        "label": None,
        "runs_per_case": 3,
        "suites": {
            "agent": {
                "metrics": {"reliable_pass_rate": 0.5, "any_pass_rate": 0.8},
                "cases": [
                    {
                        "name": "Read and answer",
                        "metrics": {"pass_rate": 1.0, "avg_iterations": 1.0, "avg_tool_calls": 1.0},
                        "runs": [
                            {"passed": True},
                            {"passed": True},
                            {"passed": True},
                        ],
                    },
                    {
                        "name": "Create a file",
                        "metrics": {"pass_rate": 0.67, "avg_iterations": 2.0, "avg_tool_calls": 1.5},
                        "runs": [
                            {"passed": True},
                            {"passed": True},
                            {"passed": False},
                        ],
                    },
                ],
            },
        },
    }
    output = _capture(print_summary, data)
    assert "Read and answer" in output
    assert "3/3" in output


def test_print_delta_report():
    deltas = {
        "speed": {
            "avg_tok_s": {"current": 25.0, "previous": 20.0, "delta": 5.0, "delta_pct": 25.0},
            "avg_ttft_ms": {"current": 180.0, "previous": 200.0, "delta": -20.0, "delta_pct": -10.0},
        },
    }
    output = _capture(print_delta_report, deltas, current_label="current", previous_label="previous")
    assert "25.0" in output
    assert "+25.0%" in output
