import json
from pathlib import Path
from benchmarks.suites.agent import AgentSuite, AGENT_CASES, base_setup


def test_agent_suite_registration():
    from benchmarks.suites import SUITE_REGISTRY
    assert "agent" in SUITE_REGISTRY


def test_agent_cases_count():
    assert len(AGENT_CASES) == 9


def test_agent_cases_have_required_fields():
    for case in AGENT_CASES:
        assert "name" in case
        assert "level" in case
        assert "task" in case
        assert "setup" in case
        assert "verify" in case
        assert callable(case["setup"])
        assert callable(case["verify"])


def test_base_setup_creates_permissions(tmp_path):
    base_setup(tmp_path)
    perms_file = tmp_path / ".local-chat-llm-permissions"
    assert perms_file.exists()
    data = json.loads(perms_file.read_text())
    assert data["read_file"] == "allow"
    assert data["write_file"] == "allow"
    assert data["run_command"] == "allow"


def test_case1_setup_and_verify(tmp_path):
    case = AGENT_CASES[0]
    case["setup"](tmp_path)
    assert (tmp_path / "info.txt").exists()
    content = (tmp_path / "info.txt").read_text()
    assert "Alice Chen" in content


def test_case2_verify_pass(tmp_path):
    case = AGENT_CASES[1]
    case["setup"](tmp_path)
    (tmp_path / "greeting.txt").write_text("Hello, World!")
    assert case["verify"](tmp_path, "I created the file.") is True


def test_case2_verify_fail(tmp_path):
    case = AGENT_CASES[1]
    case["setup"](tmp_path)
    assert case["verify"](tmp_path, "Done.") is False


def test_case3_setup(tmp_path):
    case = AGENT_CASES[2]
    case["setup"](tmp_path)
    py_files = list((tmp_path / "src").glob("*.py"))
    txt_files = list((tmp_path / "src").glob("*.txt"))
    assert len(py_files) == 5
    assert len(txt_files) == 3


def test_case4_setup_edge_case(tmp_path):
    case = AGENT_CASES[3]
    case["setup"](tmp_path)
    config_content = (tmp_path / "config.py").read_text()
    assert "TODO" in config_content
    assert "# TODO" not in config_content


def test_case5_verify_pass(tmp_path):
    case = AGENT_CASES[4]
    case["setup"](tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({
        "host": "localhost", "port": 8080, "debug": True
    }))
    assert case["verify"](tmp_path, "Done.") is True


def test_case5_verify_fail_wrong_port(tmp_path):
    case = AGENT_CASES[4]
    case["setup"](tmp_path)
    assert case["verify"](tmp_path, "Done.") is False


def test_case5_verify_fail_corrupted(tmp_path):
    case = AGENT_CASES[4]
    case["setup"](tmp_path)
    (tmp_path / "config.json").write_text(json.dumps({
        "host": "0.0.0.0", "port": 8080, "debug": True
    }))
    assert case["verify"](tmp_path, "Done.") is False
