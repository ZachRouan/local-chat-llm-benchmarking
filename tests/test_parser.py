from benchmarks.parser import parse_stats_line, parse_tool_call_line, parse_tool_result_line


def test_parse_stats_line_full():
    line = "1653 tokens in 73.0s (22.7 tok/s) · context: 1,676/100,096 (2%)"
    result = parse_stats_line(line)
    assert result is not None
    assert result["total_tokens"] == 1653
    assert result["duration_s"] == 73.0
    assert result["tok_s"] == 22.7
    assert result["context_used"] == 1676
    assert result["context_max"] == 100096
    assert result["context_pct"] == 2


def test_parse_stats_line_no_context():
    line = "527 tokens in 22.2s (23.7 tok/s)"
    result = parse_stats_line(line)
    assert result is not None
    assert result["total_tokens"] == 527
    assert result["tok_s"] == 23.7
    assert result["context_used"] is None


def test_parse_stats_line_no_match():
    result = parse_stats_line("You > ")
    assert result is None


def test_parse_stats_line_tokens_only():
    line = "42 tokens"
    result = parse_stats_line(line)
    assert result is not None
    assert result["total_tokens"] == 42
    assert result["tok_s"] is None


def test_parse_tool_call_line():
    line = "→ read_file: main.py"
    result = parse_tool_call_line(line)
    assert result is not None
    assert result["tool_name"] == "read_file"
    assert result["summary"] == "main.py"


def test_parse_tool_call_line_no_match():
    result = parse_tool_call_line("some random text")
    assert result is None


def test_parse_tool_result_success():
    line = "  ✓ (42 lines)"
    result = parse_tool_result_line(line)
    assert result is not None
    assert result["success"] is True


def test_parse_tool_result_failure():
    line = "  ✗ Error: FileNotFoundError: no such file"
    result = parse_tool_result_line(line)
    assert result is not None
    assert result["success"] is False
    assert "FileNotFoundError" in result["message"]


def test_parse_tool_result_no_match():
    result = parse_tool_result_line("normal text")
    assert result is None
