import json
from pathlib import Path
from benchmarks.suites.e2e_project import E2EProjectSuite, E2E_CASES


def test_e2e_suite_registration():
    from benchmarks.suites import SUITE_REGISTRY
    assert "e2e_project" in SUITE_REGISTRY


def test_e2e_cases_count():
    assert len(E2E_CASES) == 16


def test_e2e_levels_5_through_10():
    levels = {c["level"] for c in E2E_CASES}
    assert levels == {5, 6, 7, 8, 9, 10}


def test_case10_verify_fail_missing(tmp_path):
    case = E2E_CASES[0]
    case["setup"](tmp_path)
    assert case["verify"](tmp_path, "Done.") is False


def test_case11_verify_fail_missing(tmp_path):
    case = E2E_CASES[1]
    case["setup"](tmp_path)
    assert case["verify"](tmp_path, "Done.") is False
