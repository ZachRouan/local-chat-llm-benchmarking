"""Parse llama-chat stdout lines — stats, tool calls, tool results."""

from __future__ import annotations

import re


# Matches: "1653 tokens in 73.0s (22.7 tok/s) · context: 1,676/100,096 (2%)"
# Also:    "527 tokens in 22.2s (23.7 tok/s)"
# Also:    "42 tokens"
_STATS_RE = re.compile(
    r"(\d+)\s+tokens"
    r"(?:\s+in\s+([\d.]+)s\s+\(([\d.]+)\s+tok/s\))?"
    r"(?:\s+·\s+context:\s+([\d,]+)/([\d,]+)\s+\((\d+)%\))?"
)

# Matches: "→ read_file: main.py"
_TOOL_CALL_RE = re.compile(r"→\s+(\w+):\s+(.*)")

# Matches: "  ✓ ..." or "  ✗ ..."
_TOOL_RESULT_SUCCESS_RE = re.compile(r"\s*✓\s*(.*)")
_TOOL_RESULT_FAILURE_RE = re.compile(r"\s*✗\s*(.*)")


def parse_stats_line(line: str) -> dict | None:
    """Parse a stats line into a metrics dict. Returns None if not a stats line."""
    m = _STATS_RE.search(line)
    if not m:
        return None
    total_tokens = int(m.group(1))
    duration_s = float(m.group(2)) if m.group(2) else None
    tok_s = float(m.group(3)) if m.group(3) else None
    context_used = int(m.group(4).replace(",", "")) if m.group(4) else None
    context_max = int(m.group(5).replace(",", "")) if m.group(5) else None
    context_pct = int(m.group(6)) if m.group(6) else None
    return {
        "total_tokens": total_tokens,
        "duration_s": duration_s,
        "tok_s": tok_s,
        "context_used": context_used,
        "context_max": context_max,
        "context_pct": context_pct,
    }


def parse_tool_call_line(line: str) -> dict | None:
    """Parse a tool call line. Returns None if not a tool call line."""
    m = _TOOL_CALL_RE.search(line)
    if not m:
        return None
    return {"tool_name": m.group(1), "summary": m.group(2).strip()}


def parse_tool_result_line(line: str) -> dict | None:
    """Parse a tool result line. Returns None if not a tool result line."""
    m = _TOOL_RESULT_SUCCESS_RE.search(line)
    if m:
        return {"success": True, "message": m.group(1).strip()}
    m = _TOOL_RESULT_FAILURE_RE.search(line)
    if m:
        return {"success": False, "message": m.group(1).strip()}
    return None
