"""AppClient — drives local-chat-llm as a subprocess."""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from benchmarks.parser import parse_stats_line, parse_tool_call_line, parse_tool_result_line


class AppClientError(Exception):
    """Raised when the chat app subprocess fails."""


@dataclass
class PromptResult:
    """Result of sending a single prompt to the chat app."""
    response_text: str
    metrics: dict
    tool_log: list[dict] = field(default_factory=list)


class AppClient:
    """Wraps the local-chat-llm subprocess for benchmarking."""

    _PROMPT_RE = re.compile(r"^(You|Agent) > $")
    _MENU_CHOICE_RE = re.compile(r"\[(\d+)\]")
    _RESUME_RE = re.compile(r"Resume previous session.*\?", re.IGNORECASE)
    _TIMEOUT = 120  # seconds

    def __init__(
        self,
        app_path: str,
        server: str,
        env_overrides: dict[str, str] | None = None,
    ):
        self.app_path = app_path
        self.server = server
        self.model: str | None = None
        self.context_length: int | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._env_overrides = env_overrides or {}

    async def start(self) -> None:
        """Launch the chat app and navigate through startup menus."""
        env = os.environ.copy()
        env["LLAMA_SERVERS"] = self.server
        env.update(self._env_overrides)

        self._process = await asyncio.create_subprocess_exec(
            "python", str(Path(self.app_path) / "main.py"),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        await self._navigate_startup()

    async def _navigate_startup(self) -> None:
        """Read startup output, handle model selection and session resume."""
        buffer = ""
        while True:
            line = await self._read_line()
            buffer += line

            # Session resume prompt
            if self._RESUME_RE.search(line):
                await self._write("n\n")
                continue

            # Model selection menu — pick the first selectable option
            if "Select a model:" in buffer:
                while "Choice:" not in buffer:
                    line = await self._read_line()
                    buffer += line
                matches = self._MENU_CHOICE_RE.findall(buffer)
                if matches:
                    await self._write(f"{matches[0]}\n")
                buffer = ""
                continue

            # Banner with model info — extract context length
            if "Context" in line and "tokens" in line:
                m = re.search(r"([\d,]+)\s+tokens", line)
                if m:
                    self.context_length = int(m.group(1).replace(",", ""))

            # Ready for input
            if self._PROMPT_RE.search(line.strip()):
                break

    async def send_prompt(self, text: str) -> PromptResult:
        """Send a prompt and collect the full response with metrics."""
        started_at = time.monotonic()
        await self._write(text + "\n")

        lines: list[str] = []
        first_output_at: float | None = None

        while True:
            line = await self._read_line()

            if self._PROMPT_RE.search(line.strip()):
                break

            if first_output_at is None and line.strip():
                first_output_at = time.monotonic()

            lines.append(line)

        if first_output_at is None:
            first_output_at = time.monotonic()

        return self._parse_response(lines, started_at, first_output_at)

    async def send_command(self, command: str) -> None:
        """Send a slash command and wait for the prompt to return."""
        await self._write(command + "\n")
        while True:
            line = await self._read_line()
            if self._PROMPT_RE.search(line.strip()):
                break

    async def stop(self) -> None:
        """Send /quit and wait for the process to exit."""
        if self._process and self._process.returncode is None:
            try:
                await self._write("/quit\n")
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except (asyncio.TimeoutError, BrokenPipeError, OSError):
                self._process.kill()
                await self._process.wait()

    def _parse_response(
        self,
        lines: list[str],
        started_at: float,
        first_output_at: float,
    ) -> PromptResult:
        """Parse collected output lines into a PromptResult."""
        ttft_ms = (first_output_at - started_at) * 1000

        response_parts: list[str] = []
        tool_log: list[dict] = []
        stats_entries: list[dict] = []
        tool_calls = 0
        tool_errors = 0

        for line in lines:
            stats = parse_stats_line(line)
            if stats:
                stats_entries.append(stats)
                continue

            tc = parse_tool_call_line(line)
            if tc:
                tool_calls += 1
                tool_log.append({"type": "call", **tc})
                continue

            tr = parse_tool_result_line(line)
            if tr:
                if not tr["success"]:
                    tool_errors += 1
                tool_log.append({"type": "result", **tr})
                continue

            response_parts.append(line)

        metrics: dict = {"ttft_ms": round(ttft_ms, 1)}

        if stats_entries:
            last = stats_entries[-1]
            metrics["tok_s"] = last.get("tok_s")
            metrics["total_tokens"] = last.get("total_tokens")
            metrics["duration_s"] = last.get("duration_s")
            metrics["context_used"] = last.get("context_used")
            metrics["context_max"] = last.get("context_max")
            metrics["context_pct"] = last.get("context_pct")

        if tool_calls > 0 or len(stats_entries) > 1:
            metrics["iterations"] = len(stats_entries)
            metrics["tool_calls"] = tool_calls
            metrics["tool_errors"] = tool_errors

        response_text = "".join(response_parts).strip()

        return PromptResult(
            response_text=response_text,
            metrics=metrics,
            tool_log=tool_log,
        )

    async def _read_line(self) -> str:
        """Read a line from stdout with timeout."""
        if not self._process or not self._process.stdout:
            raise AppClientError("Process not started")
        try:
            data = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self._TIMEOUT,
            )
        except asyncio.TimeoutError:
            raise AppClientError(
                f"Timeout: no output from chat app in {self._TIMEOUT}s"
            )
        if not data:
            stderr = ""
            if self._process.stderr:
                stderr_data = await self._process.stderr.read()
                stderr = stderr_data.decode(errors="replace")
            raise AppClientError(f"Chat app exited unexpectedly. stderr: {stderr}")
        return data.decode(errors="replace")

    async def _write(self, text: str) -> None:
        """Write to stdin."""
        if not self._process or not self._process.stdin:
            raise AppClientError("Process not started")
        self._process.stdin.write(text.encode())
        await self._process.stdin.drain()
