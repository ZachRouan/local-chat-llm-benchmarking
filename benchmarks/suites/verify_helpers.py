"""Utilities for functional verification of agent-built projects."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError


def run_python(work_dir: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a Python script in the work directory."""
    return subprocess.run(
        [sys.executable, *args],
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_server(work_dir: Path, script: str, *args: str) -> subprocess.Popen:
    """Start a Python server script as a background process."""
    return subprocess.Popen(
        [sys.executable, script, *args],
        cwd=work_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def stop_server(proc: subprocess.Popen) -> None:
    """Stop a server process and its process group."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.kill()
        proc.wait()


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 10) -> bool:
    """Wait until a TCP port is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.1)
    return False


def http_request(
    method: str,
    url: str,
    body: str | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Make an HTTP request. Returns (status_code, response_body)."""
    req = Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    data = body.encode() if body else None
    if data and "Content-Type" not in (headers or {}):
        req.add_header("Content-Type", "application/json")
    try:
        with urlopen(req, data, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except URLError as e:
        if hasattr(e, "code"):
            return e.code, e.read().decode() if hasattr(e, "read") else str(e)
        raise


def tcp_send(host: str, port: int, message: str, timeout: float = 5) -> str:
    """Send a message over TCP and return the response."""
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.sendall(message.encode())
        s.settimeout(timeout)
        chunks = []
        try:
            while True:
                data = s.recv(4096)
                if not data:
                    break
                chunks.append(data.decode())
        except socket.timeout:
            pass
        return "".join(chunks)


def run_pytest(work_dir: Path) -> bool:
    """Run pytest in the work directory. Returns True if all tests pass."""
    r = run_python(work_dir, "-m", "pytest", "-v", timeout=60)
    return r.returncode == 0
