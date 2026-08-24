from benchmarks.runner import AppClient, AppClientError


def test_client_creation():
    client = AppClient(server="localhost:8082", app_python="python", app_main="main.py")
    assert client.server == "localhost:8082"
    assert client.model is None


def _bench_line(**kw):
    import json
    rec = {
        "iteration": 0, "first_token_ms": 100.0, "first_content_ms": 200.0,
        "client_duration_s": 2.0, "tokens": 50, "context_total_tokens": 350,
        "hit_max_tokens": False, "content": "", "reasoning_chars": 0,
        "tools": [], "timings": {"predicted_n": 50, "predicted_ms": 2000.0,
                                  "prompt_ms": 100.0, "prompt_per_second": 500.0},
        "system_fingerprint": "b10450-test",
    }
    rec.update(kw)
    return "@@BENCH@@" + json.dumps(rec) + "\n"


def test_parse_response_lines():
    client = AppClient(server="localhost:8082", app_python="python", app_main="main.py")
    lines = [
        "The capital of France is Paris.\n",  # rendered TTY text — ignored
        _bench_line(content="The capital of France is Paris.",
                    timings={"predicted_n": 527, "predicted_ms": 22200.0,
                             "prompt_ms": 300.0, "prompt_per_second": 400.0}),
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.1)
    assert result.metrics["tok_s"] == 23.7
    assert result.metrics["total_tokens"] == 527
    assert result.metrics["ttft_ms"] == 100.0
    assert result.metrics["timings_source"] == "server"
    assert result.response_text == "The capital of France is Paris."
    assert result.system_fingerprint == "b10450-test"


def test_parse_response_with_tool_calls():
    client = AppClient(server="localhost:8082", app_python="python", app_main="main.py")
    lines = [
        _bench_line(iteration=0, content="Let me check the file.",
                    tools=[{"name": "read_file", "ok": True}],
                    timings={"predicted_n": 100, "predicted_ms": 4000.0,
                             "prompt_ms": 50.0, "prompt_per_second": 500.0}),
        _bench_line(iteration=1, content="Done!",
                    tools=[{"name": "write_file", "ok": True}],
                    timings={"predicted_n": 50, "predicted_ms": 2000.0,
                             "prompt_ms": 50.0, "prompt_per_second": 500.0}),
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.05)
    assert result.metrics["iterations"] == 2
    assert result.metrics["tool_calls"] == 2
    assert result.metrics["tool_errors"] == 0
    assert result.metrics["total_tokens"] == 150
    assert result.metrics["tok_s"] == 25.0  # 150 tokens / 6.0s predicted
    assert result.metrics["context_used"] == 350
    assert result.response_text == "Let me check the file.\nDone!"


def test_parse_response_with_tool_errors():
    client = AppClient(server="localhost:8082", app_python="python", app_main="main.py")
    lines = [
        _bench_line(tools=[{"name": "read_file", "ok": False}]),
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.05)
    assert result.metrics["tool_errors"] == 1


def test_parse_response_fails_closed_without_bench_records():
    import pytest
    from benchmarks.runner import AppClientError
    client = AppClient(server="localhost:8082", app_python="python", app_main="main.py")
    with pytest.raises(AppClientError):
        client._parse_response(["plain text only\n"], started_at=0.0, first_output_at=0.1)


def test_model_from_banner_strips_directory():
    assert AppClient._model_from_banner("Model /mnt/models/Qwen-27B-Q4.gguf") == "Qwen-27B-Q4.gguf"


def test_model_from_banner_bare_name():
    assert AppClient._model_from_banner("Model gemma-4-26B-Q8_0.gguf · Context 81,920 tokens") == "gemma-4-26B-Q8_0.gguf"


def test_model_from_banner_missing():
    assert AppClient._model_from_banner("Context 4096 tokens") is None
