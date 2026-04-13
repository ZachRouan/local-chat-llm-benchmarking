import json
from pathlib import Path

from benchmarks.suites.e2e_project import E2E_CASES


def _case_by_name(name: str) -> dict:
    for c in E2E_CASES:
        if c["name"] == name:
            return c
    raise KeyError(f"Case not found: {name}")


# --- Registration & count ---

def test_total_cases():
    assert len(E2E_CASES) == 16


def test_levels_present():
    levels = {c["level"] for c in E2E_CASES}
    assert levels == {5, 6, 7, 8, 9, 10}


# --- Level 6 ---

def test_case12_in_registry():
    c = _case_by_name("REST API with persistence")
    assert c["level"] == 6


def test_case13_setup_creates_nothing(tmp_path):
    c = _case_by_name("Multi-step data pipeline")
    c["setup"](tmp_path)
    files = [f for f in tmp_path.iterdir() if not f.name.startswith(".")]
    assert len(files) == 0


def test_case14_setup_creates_config(tmp_path):
    c = _case_by_name("Configuration system")
    c["setup"](tmp_path)
    assert (tmp_path / "app.conf").exists()
    content = (tmp_path / "app.conf").read_text()
    assert "port: 8080" in content


def test_case13_verify_fail_missing(tmp_path):
    c = _case_by_name("Multi-step data pipeline")
    c["setup"](tmp_path)
    assert c["verify"](tmp_path, "") is False


# --- Level 7 ---

def test_case15_setup_creates_buggy_cart(tmp_path):
    c = _case_by_name("Fix a multi-file bug")
    c["setup"](tmp_path)
    assert (tmp_path / "cart.py").exists()
    assert (tmp_path / "discounts.py").exists()
    assert (tmp_path / "test_cart.py").exists()
    from benchmarks.suites.verify_helpers import run_pytest
    assert run_pytest(tmp_path) is True


def test_case16_setup_creates_spaghetti(tmp_path):
    c = _case_by_name("Untangle spaghetti code")
    c["setup"](tmp_path)
    assert (tmp_path / "analyzer.py").exists()
    assert (tmp_path / "test_analyzer.py").exists()
    assert (tmp_path / "sample.txt").exists()
    code = (tmp_path / "analyzer.py").read_text()
    assert code.count("def ") == 1
    from benchmarks.suites.verify_helpers import run_pytest
    assert run_pytest(tmp_path) is True


def test_case17_setup_creates_racy_counter(tmp_path):
    c = _case_by_name("Race condition fix")
    c["setup"](tmp_path)
    assert (tmp_path / "counter.py").exists()
    assert (tmp_path / "test_counter.py").exists()
    code = (tmp_path / "counter.py").read_text()
    assert "time.sleep" in code
    assert "Lock" not in code


# --- Level 8 ---

def test_case18_in_registry():
    c = _case_by_name("Markdown to HTML converter")
    assert c["level"] == 8


def test_case19_setup_creates_log(tmp_path):
    c = _case_by_name("Log parser with pattern matching")
    c["setup"](tmp_path)
    assert (tmp_path / "sample.log").exists()
    content = (tmp_path / "sample.log").read_text()
    assert "ERROR" in content
    assert "WARN" in content
    assert "INFO" in content


def test_case20_in_registry():
    c = _case_by_name("Key-value store with TCP protocol")
    assert c["level"] == 8


# --- Level 9 ---

def test_case21_in_registry():
    c = _case_by_name("Job queue with workers")
    assert c["level"] == 9


def test_case22_in_registry():
    c = _case_by_name("File sync tool")
    assert c["level"] == 9


def test_case23_in_registry():
    c = _case_by_name("Plugin system")
    assert c["level"] == 9


# --- Level 10 ---

def test_case24_in_registry():
    c = _case_by_name("Chat room server")
    assert c["level"] == 10


def test_case25_in_registry():
    c = _case_by_name("Database-backed CRUD app")
    assert c["level"] == 10
