import json
import socket
from pathlib import Path

from benchmarks.suites.verify_helpers import (
    run_python,
    find_free_port,
    start_server,
    stop_server,
    wait_for_port,
    http_request,
    tcp_send,
    run_pytest,
)


def test_run_python(tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("print('hello')")
    r = run_python(tmp_path, "hello.py")
    assert r.returncode == 0
    assert "hello" in r.stdout


def test_run_python_failure(tmp_path):
    script = tmp_path / "bad.py"
    script.write_text("raise ValueError('boom')")
    r = run_python(tmp_path, "bad.py")
    assert r.returncode != 0


def test_find_free_port():
    port = find_free_port()
    assert 1024 < port < 65536
    s = socket.socket()
    s.bind(("127.0.0.1", port))
    s.close()


def test_start_stop_server(tmp_path):
    script = tmp_path / "srv.py"
    script.write_text(
        "from http.server import HTTPServer, BaseHTTPRequestHandler\n"
        "import sys\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.end_headers()\n"
        "        self.wfile.write(b'ok')\n"
        "    def log_message(self, *a): pass\n"
        "s = HTTPServer(('127.0.0.1', int(sys.argv[1])), H)\n"
        "s.serve_forever()\n"
    )
    port = find_free_port()
    proc = start_server(tmp_path, "srv.py", str(port))
    assert wait_for_port(port, timeout=5)
    stop_server(proc)


def test_http_request(tmp_path):
    script = tmp_path / "srv.py"
    script.write_text(
        "from http.server import HTTPServer, BaseHTTPRequestHandler\n"
        "import sys\n"
        "class H(BaseHTTPRequestHandler):\n"
        "    def do_GET(self):\n"
        "        self.send_response(200)\n"
        "        self.send_header('Content-Type', 'application/json')\n"
        "        self.end_headers()\n"
        '        self.wfile.write(b\'{"status": "ok"}\')\n'
        "    def log_message(self, *a): pass\n"
        "s = HTTPServer(('127.0.0.1', int(sys.argv[1])), H)\n"
        "s.serve_forever()\n"
    )
    port = find_free_port()
    proc = start_server(tmp_path, "srv.py", str(port))
    wait_for_port(port, timeout=5)
    try:
        status, body = http_request("GET", f"http://127.0.0.1:{port}/test")
        assert status == 200
        assert json.loads(body)["status"] == "ok"
    finally:
        stop_server(proc)


def test_tcp_send(tmp_path):
    script = tmp_path / "echo.py"
    script.write_text(
        "import socket, sys\n"
        "s = socket.socket()\n"
        "s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
        "s.bind(('127.0.0.1', int(sys.argv[1])))\n"
        "s.listen(1)\n"
        "while True:\n"
        "    c, _ = s.accept()\n"
        "    data = c.recv(1024)\n"
        "    c.sendall(b'ECHO: ' + data)\n"
        "    c.close()\n"
    )
    port = find_free_port()
    proc = start_server(tmp_path, "echo.py", str(port))
    wait_for_port(port, timeout=5)
    try:
        response = tcp_send("127.0.0.1", port, "hello\n")
        assert "ECHO: hello" in response
    finally:
        stop_server(proc)


def test_run_pytest_pass(tmp_path):
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_pass(): assert True")
    assert run_pytest(tmp_path) is True


def test_run_pytest_fail(tmp_path):
    test_file = tmp_path / "test_bad.py"
    test_file.write_text("def test_fail(): assert False")
    assert run_pytest(tmp_path) is False
