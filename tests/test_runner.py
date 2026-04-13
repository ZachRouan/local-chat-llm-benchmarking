from benchmarks.runner import AppClient, AppClientError


def test_client_creation():
    client = AppClient(server="localhost:8082")
    assert client.server == "localhost:8082"
    assert client.model is None


def test_parse_response_lines():
    client = AppClient(server="localhost:8082")
    lines = [
        "The capital of France is Paris.\n",
        "\n",
        "527 tokens in 22.2s (23.7 tok/s) · context: 1,676/100,096 (2%)\n",
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.1)
    assert result.metrics["tok_s"] == 23.7
    assert result.metrics["total_tokens"] == 527
    assert "The capital of France is Paris." in result.response_text


def test_parse_response_with_tool_calls():
    client = AppClient(server="localhost:8082")
    lines = [
        "→ read_file: main.py\n",
        "  ✓ (42 lines)\n",
        "Let me check the file.\n",
        "100 tokens in 4.0s (25.0 tok/s) · context: 200/4096 (5%)\n",
        "→ write_file: hello.py (1 lines)\n",
        "  ✓ Wrote 1 lines to hello.py\n",
        "Done!\n",
        "50 tokens in 2.0s (25.0 tok/s) · context: 350/4096 (9%)\n",
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.05)
    assert result.metrics["iterations"] == 2
    assert result.metrics["tool_calls"] == 2
    assert result.metrics["tool_errors"] == 0
    # Tokens and duration should be summed across iterations
    assert result.metrics["total_tokens"] == 150  # 100 + 50
    assert result.metrics["duration_s"] == 6.0  # 4.0 + 2.0
    assert result.metrics["tok_s"] == 25.0  # 150 / 6.0
    # Context from last stats line
    assert result.metrics["context_used"] == 350
    assert result.metrics["context_pct"] == 9


def test_parse_response_with_tool_errors():
    client = AppClient(server="localhost:8082")
    lines = [
        "→ read_file: missing.py\n",
        "  ✗ Error: FileNotFoundError: missing.py\n",
        "50 tokens in 2.0s (25.0 tok/s)\n",
    ]
    result = client._parse_response(lines, started_at=0.0, first_output_at=0.05)
    assert result.metrics["tool_errors"] == 1
