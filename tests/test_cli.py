import subprocess
import sys


def test_cli_list():
    result = subprocess.run(
        [sys.executable, "benchmark.py", "--list"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "speed" in result.stdout
    assert "generation" in result.stdout
    assert "agent" in result.stdout
    assert "e2e_project" in result.stdout


def test_cli_no_server():
    result = subprocess.run(
        [sys.executable, "benchmark.py"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0


def test_cli_results_missing_file():
    result = subprocess.run(
        [sys.executable, "benchmark.py", "--results", "nonexistent.json"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0
