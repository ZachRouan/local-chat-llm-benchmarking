from benchmarks.parser import parse_stats_line, parse_tool_call_line, parse_tool_result_line


def test_parse_stats_line_full():
    line = "1653 tokens in 73.0s (22.7 tok/s) · context: 1,676/100,096 (2%)"
    result = parse_stats_line(line)
    assert result is not None
    stats, preceding = result
    assert stats["total_tokens"] == 1653
    assert stats["duration_s"] == 73.0
    assert stats["tok_s"] == 22.7
    assert stats["context_used"] == 1676
    assert stats["context_max"] == 100096
    assert stats["context_pct"] == 2
    assert preceding == ""


def test_parse_stats_line_no_context():
    line = "527 tokens in 22.2s (23.7 tok/s)"
    result = parse_stats_line(line)
    assert result is not None
    stats, preceding = result
    assert stats["total_tokens"] == 527
    assert stats["tok_s"] == 23.7
    assert stats["context_used"] is None
    assert preceding == ""


def test_parse_stats_line_no_match():
    result = parse_stats_line("You > ")
    assert result is None


def test_parse_stats_line_tokens_only():
    line = "42 tokens"
    result = parse_stats_line(line)
    assert result is not None
    stats, preceding = result
    assert stats["total_tokens"] == 42
    assert stats["tok_s"] is None


def test_parse_stats_line_with_preceding_text():
    line = "The author name is Alice Chen.                                                  7 tokens in 0.3s (27.2 tok/s) · context: 301/100,096 (0%)"
    result = parse_stats_line(line)
    assert result is not None
    stats, preceding = result
    assert stats["total_tokens"] == 7
    assert stats["tok_s"] == 27.2
    assert "Alice Chen" in preceding


def test_parse_context_only_line():
    line = "context: 133/100,096 (0%)"
    result = parse_stats_line(line)
    assert result is not None
    stats, preceding = result
    assert stats["total_tokens"] == 0
    assert stats["context_used"] == 133
    assert stats["context_max"] == 100096
    assert stats["context_pct"] == 0
    assert preceding == ""


def test_parse_context_only_not_in_normal_text():
    # Should not match context mentions in regular text
    result = parse_stats_line("The context window is important")
    assert result is None


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
