"""AppClient — drives local-chat-llm as a subprocess.

Metrics come from the app's machine-readable @@BENCH@@ JSON lines
(enabled via LLAMA_BENCH_JSON=1), never from scraping the rendered TTY
output — rich's renderer drops code fences, wraps lines, and buffers the
whole response in a pipe, so scraped text/timing is unusable for metrics.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


class AppClientError(Exception):
    """Raised when the chat app subprocess fails."""


BENCH_SENTINEL = "@@BENCH@@"


@dataclass
class PromptResult:
    """Result of sending a single prompt to the chat app."""
    response_text: str
    metrics: dict
    tool_log: list[dict] = field(default_factory=list)
    bench_records: list[dict] = field(default_factory=list)
    system_fingerprint: str | None = None


class AppClient:
    """Wraps the local-chat-llm subprocess for benchmarking.

    Reads stdout byte-by-byte into a buffer, since the chat app uses
    input() which writes prompts without a trailing newline.
    """

    _PROMPT_RE = re.compile(r"(You|Agent) > $")
    _CHOICE_RE = re.compile(r"Choice: $")
    _MENU_CHOICE_RE = re.compile(r"\[(\d+)\]")
    _RESUME_RE = re.compile(r"Resume previous session.*\?.*$", re.MULTILINE | re.IGNORECASE)
    _YN_RE = re.compile(r"\(y/n\)\s*$")
    _TIMEOUT = 600  # seconds

    def __init__(
        self,
        server: str,
        app_python: str | None = None,
        app_main: str | None = None,
        env_overrides: dict[str, str] | None = None,
    ):
        self.server = server
        self.model: str | None = None
        self.context_length: int | None = None
        self.last_fingerprint: str | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._env_overrides = env_overrides or {}
        # Resolve the llama-chat script to find the app's Python and main.py
        self._app_python = app_python
        self._app_main = app_main
        if not self._app_python or not self._app_main:
            self._resolve_app_paths()

    def _resolve_app_paths(self) -> None:
        """Find the app's Python interpreter and main.py from llama-chat."""
        import shutil
        import subprocess
        llama_chat = shutil.which("llama-chat")
        if not llama_chat:
            raise AppClientError("llama-chat not found in PATH")
        # Resolve symlinks to find the project directory
        resolved = Path(llama_chat).resolve()
        project_dir = resolved.parent
        self._app_main = self._app_main or str(project_dir / "main.py")
        self._app_python = self._app_python or str(project_dir / ".venv" / "bin" / "python")
        if not Path(self._app_main).exists():
            raise AppClientError(f"main.py not found at {self._app_main}")
        if not Path(self._app_python).exists():
            raise AppClientError(f"Python not found at {self._app_python}")

    async def start(self, cwd: str | Path | None = None) -> None:
        """Launch the chat app and navigate through startup menus.

        Args:
            cwd: Working directory to launch the app from. The app uses
                 this as its project directory (tools operate relative to it).
        """
        env = os.environ.copy()
        env["LLAMA_SERVERS"] = self.server
        env["PYTHONUNBUFFERED"] = "1"
        env["LLAMA_BENCH_JSON"] = "1"
        env.update(self._env_overrides)

        self._process = await asyncio.create_subprocess_exec(
            self._app_python, "-u", self._app_main,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(cwd) if cwd else None,
        )

        await self._navigate_startup()

    async def _navigate_startup(self) -> None:
        """Read startup output, handle model selection and session resume."""
        all_output = ""
        while True:
            chunk = await self._read_until_prompt_or_line()
            all_output += chunk

            # Session resume prompt (y/n)
            if self._RESUME_RE.search(chunk) or self._YN_RE.search(chunk):
                await self._write("n\n")
                continue

            # Model selection — "Choice: " prompt
            if self._CHOICE_RE.search(chunk):
                # Menu items were in earlier lines — search all output
                matches = self._MENU_CHOICE_RE.findall(all_output)
                if matches:
                    await self._write(f"{matches[0]}\n")
                continue

            # Banner with context length
            if "Context" in chunk and "tokens" in chunk:
                m = re.search(r"([\d,]+)\s+tokens", chunk)
                if m:
                    self.context_length = int(m.group(1).replace(",", ""))

            # Extract model name from banner
            if "Model" in chunk:
                name = self._model_from_banner(chunk)
                if name:
                    self.model = name

            # Ready for input
            if self._PROMPT_RE.search(chunk):
                break

    @staticmethod
    def _model_from_banner(chunk: str) -> str | None:
        """Extract the model name from the startup banner.

        The app prints whatever llama-server reports, which is the full
        GGUF path when the server was started with ``-m /path/to/model.gguf``.
        Keep only the final path component so result filenames and
        ``--compare`` matching don't depend on where the model lives on disk.
        """
        m = re.search(r"Model\s+(\S+)", chunk)
        if not m:
            return None
        return PurePosixPath(m.group(1).strip()).name or None

    async def send_prompt(self, text: str) -> PromptResult:
        """Send a prompt and collect the full response with metrics."""
        started_at = time.monotonic()
        await self._write(text + "\n")

        lines: list[str] = []
        first_output_at: float | None = None

        while True:
            chunk = await self._read_until_prompt_or_line()

            # Check if we hit the next prompt
            if self._PROMPT_RE.search(chunk):
                # There might be a final line before the prompt on the same chunk
                before_prompt = self._PROMPT_RE.sub("", chunk).strip()
                if before_prompt:
                    if first_output_at is None:
                        first_output_at = time.monotonic()
                    lines.append(before_prompt + "\n")
                break

            if first_output_at is None and chunk.strip():
                first_output_at = time.monotonic()

            lines.append(chunk)

        if first_output_at is None:
            first_output_at = time.monotonic()

        return self._parse_response(lines, started_at, first_output_at)

    async def send_command(self, command: str) -> None:
        """Send a slash command and wait for the prompt to return."""
        await self._write(command + "\n")
        while True:
            chunk = await self._read_until_prompt_or_line()
            if self._PROMPT_RE.search(chunk):
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
        """Build a PromptResult from the turn's @@BENCH@@ JSON records.

        Fails closed: if the app emitted no bench records, metrics would
        silently revert to garbage — raise instead.
        """
        records: list[dict] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith(BENCH_SENTINEL):
                try:
                    records.append(json.loads(stripped[len(BENCH_SENTINEL):]))
                except json.JSONDecodeError:
                    raise AppClientError(f"Malformed bench record: {stripped[:200]}")

        if not records:
            raise AppClientError(
                "No @@BENCH@@ records in response — app not in bench mode or turn failed"
            )

        # Answer text: the model's actual content across iterations, never
        # reasoning and never tool/command output.
        response_text = "\n".join(
            r["content"] for r in records if r.get("content")
        ).strip()

        tool_log: list[dict] = []
        tool_calls = 0
        tool_errors = 0
        for r in records:
            for t in r.get("tools", []):
                tool_calls += 1
                if not t.get("ok"):
                    tool_errors += 1
                tool_log.append({"type": "call", "tool_name": t.get("name"), "success": t.get("ok")})

        metrics: dict = {}
        first = records[0]
        if first.get("first_token_ms") is not None:
            metrics["ttft_ms"] = first["first_token_ms"]
        if first.get("first_content_ms") is not None:
            metrics["first_content_ms"] = first["first_content_ms"]

        # Prefer server-side timings (authoritative decode rate and token
        # counts); fall back to client-side stream measurements.
        predicted_n = 0
        predicted_ms = 0.0
        prompt_ms = 0.0
        have_timings = all(r.get("timings") for r in records)
        if have_timings:
            for r in records:
                t = r["timings"]
                predicted_n += t.get("predicted_n") or 0
                predicted_ms += t.get("predicted_ms") or 0.0
                prompt_ms += t.get("prompt_ms") or 0.0
            metrics["total_tokens"] = predicted_n
            metrics["duration_s"] = round((predicted_ms + prompt_ms) / 1000, 1)
            metrics["prompt_ms"] = round(prompt_ms, 1)
            if predicted_ms > 0:
                metrics["tok_s"] = round(predicted_n / (predicted_ms / 1000), 1)
            last_t = records[-1]["timings"]
            if last_t.get("prompt_per_second"):
                metrics["prefill_tok_s"] = round(last_t["prompt_per_second"], 1)
            metrics["timings_source"] = "server"
        else:
            total_tokens = sum(r.get("tokens") or 0 for r in records)
            total_duration = sum(r.get("client_duration_s") or 0 for r in records)
            metrics["total_tokens"] = total_tokens
            metrics["duration_s"] = round(total_duration, 1)
            if total_duration > 0:
                metrics["tok_s"] = round(total_tokens / total_duration, 1)
            metrics["timings_source"] = "client"

        last = records[-1]
        metrics["context_used"] = last.get("context_total_tokens")
        metrics["hit_max_tokens"] = any(r.get("hit_max_tokens") for r in records)
        metrics["reasoning_chars"] = sum(r.get("reasoning_chars") or 0 for r in records)

        if tool_calls > 0 or len(records) > 1:
            metrics["iterations"] = len(records)
            metrics["tool_calls"] = tool_calls
            metrics["tool_errors"] = tool_errors

        fingerprint = next(
            (r["system_fingerprint"] for r in records if r.get("system_fingerprint")), None
        )
        if fingerprint:
            self.last_fingerprint = fingerprint

        return PromptResult(
            response_text=response_text,
            metrics=metrics,
            tool_log=tool_log,
            bench_records=records,
            system_fingerprint=fingerprint,
        )

    async def _read_until_prompt_or_line(self) -> str:
        """Read from stdout until we get a complete line or an input prompt.

        The chat app uses input() which writes prompts like "You > " and
        "Choice: " without a trailing newline. We read byte-by-byte into
        a buffer and return when we see either a newline or a known prompt
        pattern at the end of the buffer.
        """
        if not self._process or not self._process.stdout:
            raise AppClientError("Process not started")

        buf = bytearray()
        deadline = asyncio.get_event_loop().time() + self._TIMEOUT

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise AppClientError(
                    f"Timeout: no output from chat app in {self._TIMEOUT}s"
                )

            try:
                byte = await asyncio.wait_for(
                    self._process.stdout.read(1),
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                raise AppClientError(
                    f"Timeout: no output from chat app in {self._TIMEOUT}s"
                )

            if not byte:
                stderr = ""
                if self._process.stderr:
                    stderr_data = await self._process.stderr.read()
                    stderr = stderr_data.decode(errors="replace")
                raise AppClientError(f"Chat app exited unexpectedly. stderr: {stderr}")

            buf.extend(byte)
            text = buf.decode(errors="replace")

            # Complete line
            if byte == b"\n":
                return text

            # Check for input prompts (no newline)
            if self._PROMPT_RE.search(text):
                return text
            if self._CHOICE_RE.search(text):
                return text
            if self._YN_RE.search(text):
                return text

    async def _write(self, text: str) -> None:
        """Write to stdin."""
        if not self._process or not self._process.stdin:
            raise AppClientError("Process not started")
        self._process.stdin.write(text.encode())
        await self._process.stdin.drain()
