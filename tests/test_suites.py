"""Tests for the 5 performance benchmark suites."""

from benchmarks.suites.speed import SpeedSuite
from benchmarks.suites.generation import GenerationSuite
from benchmarks.suites.code import CodeSuite, extract_python_code
from benchmarks.suites.context import ContextSuite
from benchmarks.suites.multiturn import MultiTurnSuite
from benchmarks.suites import SUITE_REGISTRY


# --- Registration ---

def test_speed_suite_registered():
    assert "speed" in SUITE_REGISTRY


def test_generation_suite_registered():
    assert "generation" in SUITE_REGISTRY


def test_code_suite_registered():
    assert "code" in SUITE_REGISTRY


def test_context_suite_registered():
    assert "context" in SUITE_REGISTRY


def test_multiturn_suite_registered():
    assert "multiturn" in SUITE_REGISTRY


# --- Speed ---

def test_speed_has_prompts():
    suite = SpeedSuite()
    assert len(suite.prompts) >= 5
    for name, prompt in suite.prompts:
        assert isinstance(name, str)
        assert isinstance(prompt, str)


def test_speed_aggregate():
    suite = SpeedSuite()
    case_metrics = [
        {"tok_s": 20.0, "ttft_ms": 100.0},
        {"tok_s": 30.0, "ttft_ms": 200.0},
    ]
    agg = suite._aggregate(case_metrics)
    assert agg["avg_tok_s"] == 25.0
    assert agg["avg_ttft_ms"] == 150.0


# --- Generation ---

def test_generation_has_prompts():
    suite = GenerationSuite()
    assert len(suite.prompts) >= 2
    for name, prompt in suite.prompts:
        assert len(prompt) > 20


# --- Code ---

def test_extract_python_code_fenced():
    text = "Here is the code:\n```python\ndef add(a, b):\n    return a + b\n```\nDone."
    code = extract_python_code(text)
    assert "def add(a, b):" in code


def test_extract_python_code_unfenced():
    text = "def add(a, b):\n    return a + b"
    code = extract_python_code(text)
    assert "def add(a, b):" in code


def test_extract_python_code_none():
    text = "I don't know how to do that."
    code = extract_python_code(text)
    assert code == ""


def test_code_validate_syntax_valid():
    suite = CodeSuite()
    assert suite._validate_syntax("def add(a, b):\n    return a + b\n") is True


def test_code_validate_syntax_invalid():
    suite = CodeSuite()
    assert suite._validate_syntax("def add(a, b)\n    return a + b\n") is False


# --- Context ---

def test_context_filler_length():
    suite = ContextSuite()
    text = suite._generate_filler(1000)
    assert len(text) >= 900
    assert len(text) <= 1200


def test_context_levels():
    suite = ContextSuite()
    assert len(suite.fill_levels) == 5
    assert suite.fill_levels[0] < suite.fill_levels[-1]


# --- Multi-turn ---

def test_multiturn_conversation():
    suite = MultiTurnSuite()
    assert len(suite.conversation) >= 5
    for name, prompt in suite.conversation:
        assert isinstance(name, str)
        assert isinstance(prompt, str)
