import json
import pytest
from pathlib import Path
from benchmarks.results import save_results, load_results, find_previous_result, compute_deltas


def test_save_and_load(tmp_path):
    data = {
        "timestamp": "2026-04-13T14:30:00Z",
        "model": "test-model",
        "server": "localhost:8082",
        "context_length": 4096,
        "label": None,
        "runs_per_case": 1,
        "suites": {
            "speed": {
                "metrics": {"avg_tok_s": 25.0},
                "cases": [],
            }
        },
    }
    path = save_results(data, tmp_path)
    assert path.exists()
    assert "test-model" in path.name
    loaded = load_results(path)
    assert loaded["model"] == "test-model"
    assert loaded["suites"]["speed"]["metrics"]["avg_tok_s"] == 25.0


def test_find_previous_result(tmp_path):
    data1 = {"timestamp": "2026-04-13T14:00:00Z", "model": "test-model", "suites": {}}
    data2 = {"timestamp": "2026-04-13T15:00:00Z", "model": "test-model", "suites": {}}
    p1 = tmp_path / "2026-04-13-1400-test-model.json"
    p2 = tmp_path / "2026-04-13-1500-test-model.json"
    p1.write_text(json.dumps(data1))
    p2.write_text(json.dumps(data2))

    prev = find_previous_result("test-model", tmp_path, exclude=p2)
    assert prev is not None
    loaded = load_results(prev)
    assert loaded["timestamp"] == "2026-04-13T14:00:00Z"


def test_find_previous_result_none(tmp_path):
    prev = find_previous_result("nonexistent", tmp_path)
    assert prev is None


def test_compute_deltas():
    current = {
        "suites": {
            "speed": {"metrics": {"avg_tok_s": 25.0, "avg_ttft_ms": 180}},
        }
    }
    previous = {
        "suites": {
            "speed": {"metrics": {"avg_tok_s": 20.0, "avg_ttft_ms": 200}},
        }
    }
    deltas = compute_deltas(current, previous)
    assert deltas["speed"]["avg_tok_s"]["current"] == 25.0
    assert deltas["speed"]["avg_tok_s"]["previous"] == 20.0
    assert deltas["speed"]["avg_tok_s"]["delta_pct"] == pytest.approx(25.0)


def test_compute_deltas_missing_suite():
    current = {"suites": {"speed": {"metrics": {"avg_tok_s": 25.0}}}}
    previous = {"suites": {}}
    deltas = compute_deltas(current, previous)
    assert "speed" in deltas
    assert deltas["speed"]["avg_tok_s"]["previous"] is None
