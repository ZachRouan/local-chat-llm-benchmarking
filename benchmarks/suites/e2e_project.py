"""E2E project suite — full project creation test cases (levels 5-10)."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import TYPE_CHECKING

from benchmarks.suites import register
from benchmarks.suites.agent import base_setup, _make_work_dir
from benchmarks.suites.base import BenchmarkSuite, SuiteResult, CaseResult, RunResult
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

if TYPE_CHECKING:
    from benchmarks.runner import AppClient


# ---- Case 10: CLI tool ----

def _case10_setup(work_dir: Path) -> None:
    pass

def _case10_verify(work_dir: Path, response: str) -> bool:
    taskman = work_dir / "taskman.py"
    if not taskman.exists():
        return False

    r = run_python(work_dir, "taskman.py", "add", "Buy milk")
    if r.returncode != 0:
        return False
    r = run_python(work_dir, "taskman.py", "add", "Write tests")
    if r.returncode != 0:
        return False

    r = run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False
    if "Buy milk" not in r.stdout or "Write tests" not in r.stdout:
        return False

    r = run_python(work_dir, "taskman.py", "done", "1")
    if r.returncode != 0:
        return False

    r = run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False
    output_lower = r.stdout.lower()
    if "done" not in output_lower and "✓" not in r.stdout and "[x]" not in output_lower:
        return False

    r = run_python(work_dir, "taskman.py", "clear")
    if r.returncode != 0:
        return False

    r = run_python(work_dir, "taskman.py", "list")
    if r.returncode != 0:
        return False

    tasks_file = work_dir / "tasks.json"
    if tasks_file.exists():
        try:
            json.loads(tasks_file.read_text())
        except json.JSONDecodeError:
            return False

    test_file = work_dir / "test_taskman.py"
    if test_file.exists():
        r = run_python(work_dir, "-m", "pytest", "test_taskman.py", "-v")
        if r.returncode != 0:
            return False

    return True


# ---- Case 11: Multi-module project ----

def _case11_setup(work_dir: Path) -> None:
    pass

def _case11_verify(work_dir: Path, response: str) -> bool:
    for name in ["shortener.py", "storage.py", "cli.py"]:
        if not (work_dir / name).exists():
            return False

    r = run_python(work_dir, "cli.py", "shorten", "https://example.com")
    if r.returncode != 0:
        return False
    code = r.stdout.strip().split()[-1]
    if not code:
        return False

    r = run_python(work_dir, "cli.py", "resolve", code)
    if r.returncode != 0:
        return False
    if "https://example.com" not in r.stdout:
        return False

    test_files = list(work_dir.glob("test_*.py"))
    if test_files:
        r = run_python(work_dir, "-m", "pytest", "-v")
        if r.returncode != 0:
            return False

    return True


# ---- Case 12: REST API with persistence ----

def _case12_setup(work_dir: Path) -> None:
    pass

def _case12_verify(work_dir: Path, response: str) -> bool:
    port = find_free_port()
    # Try common server filenames
    server_script = None
    for name in ["server.py", "app.py", "api.py", "main.py"]:
        if (work_dir / name).exists():
            server_script = name
            break
    if not server_script:
        return False

    proc = start_server(work_dir, server_script, str(port))
    if not wait_for_port(port, timeout=10):
        stop_server(proc)
        return False
    try:
        base = f"http://127.0.0.1:{port}"

        # Create 2 notes
        status, body = http_request("POST", f"{base}/notes",
            body=json.dumps({"title": "Note 1", "body": "First note"}))
        if status not in (200, 201):
            return False
        note1 = json.loads(body)
        if "id" not in note1:
            return False

        status, body = http_request("POST", f"{base}/notes",
            body=json.dumps({"title": "Note 2", "body": "Second note"}))
        if status not in (200, 201):
            return False

        # List notes
        status, body = http_request("GET", f"{base}/notes")
        if status != 200:
            return False
        notes = json.loads(body)
        if isinstance(notes, dict):
            notes = notes.get("notes", notes.get("data", []))
        if not isinstance(notes, list) or len(notes) < 2:
            return False

        # Get one note
        note_id = note1.get("id", 1)
        status, body = http_request("GET", f"{base}/notes/{note_id}")
        if status != 200:
            return False

        # Delete one note
        status, _ = http_request("DELETE", f"{base}/notes/{note_id}")
        if status not in (200, 204):
            return False

        # Verify deletion
        status, body = http_request("GET", f"{base}/notes")
        if status != 200:
            return False

        # Restart and check persistence
        stop_server(proc)
        proc = start_server(work_dir, server_script, str(port))
        if not wait_for_port(port, timeout=10):
            return False
        status, body = http_request("GET", f"{base}/notes")
        if status != 200:
            return False

        stop_server(proc)
        return run_pytest(work_dir)
    except Exception:
        return False
    finally:
        stop_server(proc)


# ---- Case 13: Multi-step data pipeline ----

def _case13_setup(work_dir: Path) -> None:
    pass

def _case13_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "generate.py")
    if r.returncode != 0:
        return False
    csv_files = list(work_dir.glob("*.csv"))
    if not csv_files:
        return False
    lines = csv_files[0].read_text().strip().split("\n")
    if len(lines) < 100:
        return False

    r = run_python(work_dir, "transform.py")
    if r.returncode != 0:
        return False
    json_files = [f for f in work_dir.glob("*.json") if f.name != ".local-chat-llm-permissions"]
    if not json_files:
        return False
    try:
        data = json.loads(json_files[0].read_text())
    except json.JSONDecodeError:
        return False
    if not isinstance(data, (dict, list)):
        return False

    r = run_python(work_dir, "report.py")
    if r.returncode != 0:
        return False
    if len(r.stdout.strip()) < 10:
        return False

    return run_pytest(work_dir)


# ---- Case 14: Configuration system ----

def _case14_setup(work_dir: Path) -> None:
    (work_dir / "app.conf").write_text(
        "# Application config\n"
        "port: 8080\n"
        "debug: true\n"
        "name: myapp\n"
        "timeout: 30.5\n"
    )

def _case14_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "config_tool.py", "get", "port")
    if r.returncode != 0 or "8080" not in r.stdout:
        return False

    r = run_python(work_dir, "config_tool.py", "list")
    if r.returncode != 0 or "port" not in r.stdout:
        return False

    r = run_python(work_dir, "config_tool.py", "set", "port", "9090")
    if r.returncode != 0:
        return False
    r = run_python(work_dir, "config_tool.py", "get", "port")
    if r.returncode != 0 or "9090" not in r.stdout:
        return False

    env = os.environ.copy()
    env["APP_PORT"] = "3000"
    r = subprocess.run(
        [sys.executable, "config_tool.py", "get", "port"],
        cwd=work_dir, capture_output=True, text=True, timeout=10, env=env,
    )
    if r.returncode != 0 or "3000" not in r.stdout:
        return False

    return run_pytest(work_dir)


# ---- Case 15: Fix a multi-file bug ----

def _case15_setup(work_dir: Path) -> None:
    (work_dir / "discounts.py").write_text(textwrap.dedent("""\
        CODES = {
            "SAVE20": 0.20,
            "HALF": 0.50,
            "TENOFF": 0.10,
        }

        def get_discount(code):
            return CODES.get(code.upper(), 0.0)
    """))

    (work_dir / "cart.py").write_text(textwrap.dedent("""\
        from discounts import get_discount

        class Cart:
            def __init__(self):
                self._items = []
                self._discount_rate = 0.0
                self._discounted_total = None

            def add_item(self, name, price, qty=1):
                self._items.append({"name": name, "price": price, "qty": qty})

            def apply_discount(self, code):
                rate = get_discount(code)
                if rate == 0.0:
                    raise ValueError(f"Invalid discount code: {code}")
                self._discount_rate = rate
                # Cache the discounted total at time of application
                subtotal = sum(i["price"] * i["qty"] for i in self._items)
                self._discounted_total = subtotal * (1 - rate)

            def get_total(self):
                if self._discounted_total is not None:
                    return self._discounted_total
                return sum(i["price"] * i["qty"] for i in self._items)
    """))

    (work_dir / "test_cart.py").write_text(textwrap.dedent("""\
        from cart import Cart

        def test_add_items():
            c = Cart()
            c.add_item("Widget", 10.0, 2)
            assert c.get_total() == 20.0

        def test_apply_discount():
            c = Cart()
            c.add_item("Widget", 10.0, 2)
            c.apply_discount("SAVE20")
            assert c.get_total() == 16.0

        def test_invalid_discount():
            c = Cart()
            c.add_item("Widget", 10.0)
            try:
                c.apply_discount("FAKE")
                assert False, "Should have raised"
            except ValueError:
                pass
    """))

def _case15_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "-m", "pytest", "test_cart.py", "-v")
    if r.returncode != 0:
        return False

    r = run_python(work_dir, "-c", textwrap.dedent("""\
        from cart import Cart
        c = Cart()
        c.add_item("A", 10.0)
        c.apply_discount("SAVE20")
        c.add_item("B", 5.0)
        total = c.get_total()
        assert total > 10.0, f"Total {total} doesn't include item added after discount"
        print(f"OK: total={total}")
    """))
    if r.returncode != 0:
        return False

    return run_pytest(work_dir)


# ---- Case 16: Untangle spaghetti code ----

def _case16_setup(work_dir: Path) -> None:
    (work_dir / "sample.txt").write_text(textwrap.dedent("""\
        The quick brown fox jumps over the lazy dog. This is a simple sentence.
        Python is a popular programming language. It is used for web development and data science.
        The weather today is sunny and warm. Birds are singing in the trees outside my window.
        Machine learning is transforming many industries. Data is the new oil in the digital economy.
        Short one. Another short one here too.
        The longest sentence in this document is intentionally made to be quite long so that the analyzer can correctly identify it as the longest sentence among all the sentences in this sample text file.
    """))

    (work_dir / "analyzer.py").write_text(textwrap.dedent("""\
        import re
        from collections import Counter

        def analyze(filepath):
            with open(filepath) as f:
                text = f.read()
            words = re.findall(r'[a-zA-Z]+', text.lower())
            word_count = len(words)
            word_freq = Counter(words)
            top_words = word_freq.most_common(5)
            total_len = sum(len(w) for w in words)
            avg_word_length = total_len / word_count if word_count > 0 else 0
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]
            sentence_count = len(sentences)
            longest_sentence = ""
            shortest_sentence = ""
            max_len = 0
            min_len = float('inf')
            for s in sentences:
                s_words = len(re.findall(r'[a-zA-Z]+', s))
                if s_words > max_len:
                    max_len = s_words
                    longest_sentence = s
                if s_words < min_len and s_words > 0:
                    min_len = s_words
                    shortest_sentence = s
            unique_words = len(set(words))
            char_count = len(text)
            line_count = text.count('\\n') + 1
            avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0
            return {
                "word_count": word_count,
                "unique_words": unique_words,
                "char_count": char_count,
                "line_count": line_count,
                "sentence_count": sentence_count,
                "avg_word_length": round(avg_word_length, 2),
                "avg_sentence_length": round(avg_sentence_length, 2),
                "top_words": top_words,
                "longest_sentence": longest_sentence,
                "shortest_sentence": shortest_sentence,
            }
    """))

    # Pre-compute expected results
    import re
    from collections import Counter
    text = (work_dir / "sample.txt").read_text()
    words = re.findall(r'[a-zA-Z]+', text.lower())
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    expected = {
        "word_count": len(words),
        "unique_words": len(set(words)),
        "sentence_count": len(sentences),
    }
    (work_dir / ".expected.json").write_text(json.dumps(expected))

    (work_dir / "test_analyzer.py").write_text(textwrap.dedent("""\
        from analyzer import analyze

        def test_analyze_returns_dict():
            result = analyze("sample.txt")
            assert isinstance(result, dict)

        def test_word_count():
            result = analyze("sample.txt")
            assert result["word_count"] > 0

        def test_top_words():
            result = analyze("sample.txt")
            assert len(result["top_words"]) == 5

        def test_sentences():
            result = analyze("sample.txt")
            assert result["sentence_count"] > 0
            assert len(result["longest_sentence"]) > len(result["shortest_sentence"])
    """))

def _case16_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "-m", "pytest", "test_analyzer.py", "-v")
    if r.returncode != 0:
        return False

    code = (work_dir / "analyzer.py").read_text()
    in_func = False
    func_lines = 0
    for line in code.split("\n"):
        stripped = line.strip()
        if stripped.startswith("def "):
            if in_func and func_lines > 20:
                return False
            in_func = True
            func_lines = 0
        elif in_func:
            if stripped:
                func_lines += 1
    if in_func and func_lines > 20:
        return False

    func_count = code.count("\ndef ") + (1 if code.startswith("def ") else 0)
    if func_count < 4:
        return False

    expected = json.loads((work_dir / ".expected.json").read_text())
    r = run_python(work_dir, "-c",
        "import json; from analyzer import analyze; "
        "r = analyze('sample.txt'); print(json.dumps({'word_count': r['word_count'], "
        "'unique_words': r['unique_words'], 'sentence_count': r['sentence_count']}))"
    )
    if r.returncode != 0:
        return False
    actual = json.loads(r.stdout)
    if actual["word_count"] != expected["word_count"]:
        return False
    if actual["sentence_count"] != expected["sentence_count"]:
        return False

    return run_pytest(work_dir)


# ---- Case 17: Race condition fix ----

def _case17_setup(work_dir: Path) -> None:
    (work_dir / "counter.py").write_text(textwrap.dedent("""\
        import time

        class Counter:
            def __init__(self):
                self._value = 0

            def increment(self):
                current = self._value
                time.sleep(0.001)
                self._value = current + 1

            def decrement(self):
                current = self._value
                time.sleep(0.001)
                self._value = current - 1

            @property
            def value(self):
                return self._value
    """))

    (work_dir / "test_counter.py").write_text(textwrap.dedent("""\
        import threading
        from counter import Counter

        def test_threaded_increment():
            c = Counter()
            threads = []
            for _ in range(10):
                t = threading.Thread(target=lambda: [c.increment() for _ in range(100)])
                threads.append(t)
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            assert c.value == 1000, f"Expected 1000, got {c.value}"
    """))

def _case17_verify(work_dir: Path, response: str) -> bool:
    for _ in range(5):
        r = run_python(work_dir, "-m", "pytest", "test_counter.py", "-v")
        if r.returncode != 0:
            return False

    code = (work_dir / "counter.py").read_text()
    has_lock = "Lock" in code or "RLock" in code or "Semaphore" in code
    if not has_lock:
        return False

    return run_pytest(work_dir)


# ---- Case 18: Markdown to HTML converter ----

def _case18_setup(work_dir: Path) -> None:
    pass

def _case18_verify(work_dir: Path, response: str) -> bool:
    test_md = work_dir / "test_input.md"
    test_md.write_text(textwrap.dedent("""\
        # Heading 1
        ## Heading 2
        ### Heading 3

        This is a paragraph with **bold** and *italic* text.

        Here is `inline code` in a sentence.

        ```
        code block here
        multiple lines
        ```

        - Item one
        - Item **two** with bold
        - Item three

        Visit [Example](https://example.com) for more info.
    """))

    r = run_python(work_dir, "md2html.py", "test_input.md")
    if r.returncode != 0:
        return False
    html = r.stdout

    checks = [
        "<h1>" in html,
        "<h2>" in html,
        "<h3>" in html,
        "<strong>" in html or "<b>" in html,
        "<em>" in html or "<i>" in html,
        "<code>" in html,
        "<ul>" in html,
        "<li>" in html,
        "href=" in html and "example.com" in html,
    ]
    if not all(checks):
        return False

    return run_pytest(work_dir)


# ---- Case 19: Log parser with pattern matching ----

def _case19_setup(work_dir: Path) -> None:
    lines = [
        "[2026-04-13 10:00:01] INFO: Server started on port 8080",
        "[2026-04-13 10:00:15] INFO: Client connected from 192.168.1.5",
        "[2026-04-13 10:01:00] WARN: High memory usage detected",
        "[2026-04-13 10:01:25] ERROR: Database connection timeout",
        "[2026-04-13 10:02:00] INFO: Request processed in 150ms",
        "[2026-04-13 10:02:30] ERROR: Database connection timeout",
        "[2026-04-13 10:03:00] INFO: Cache cleared",
        "[2026-04-13 10:05:00] WARN: Disk space below 10%",
        "[2026-04-13 10:06:25] ERROR: File not found: /data/report.csv",
        "[2026-04-13 10:10:00] INFO: Backup completed",
        "[2026-04-13 10:15:00] ERROR: Database connection timeout",
        "[2026-04-13 10:15:30] INFO: Reconnected to database",
        "[2026-04-13 11:00:00] INFO: Hourly cleanup started",
        "[2026-04-13 11:00:05] WARN: Stale sessions found",
        "[2026-04-13 11:00:35] ERROR: Failed to clean session store",
        "[2026-04-13 11:01:00] INFO: Cleanup finished with errors",
        "[2026-04-13 11:30:00] ERROR: Connection refused by upstream",
        "[2026-04-13 12:00:00] INFO: Health check passed",
    ]
    for i in range(30):
        minute = 20 + i
        lines.insert(10 + i, f"[2026-04-13 10:{minute:02d}:00] INFO: Processing request {i+1}")
    (work_dir / "sample.log").write_text("\n".join(lines) + "\n")

def _case19_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "cli.py", "sample.log")
    if r.returncode != 0:
        return False
    output = r.stdout.lower()
    has_error_counts = any(c.isdigit() for c in output)
    has_escalation = "escalat" in output or "warn" in output
    if not has_error_counts or not has_escalation:
        return False

    return run_pytest(work_dir)


# ---- Case 20: Key-value store with TCP protocol ----

def _case20_setup(work_dir: Path) -> None:
    pass

def _case20_verify(work_dir: Path, response: str) -> bool:
    port = find_free_port()
    proc = start_server(work_dir, "server.py", str(port))
    if not wait_for_port(port, timeout=10):
        stop_server(proc)
        return False
    try:
        resp = tcp_send("127.0.0.1", port, "SET foo bar\n")
        if "OK" not in resp.upper():
            return False

        resp = tcp_send("127.0.0.1", port, "GET foo\n")
        if "bar" not in resp:
            return False

        tcp_send("127.0.0.1", port, "SET baz qux\n")

        resp = tcp_send("127.0.0.1", port, "KEYS\n")
        if "foo" not in resp or "baz" not in resp:
            return False

        resp = tcp_send("127.0.0.1", port, "DELETE foo\n")
        if "OK" not in resp.upper():
            return False

        resp = tcp_send("127.0.0.1", port, "GET foo\n")
        if "ERROR" not in resp.upper() and "NOT" not in resp.upper() and "bar" in resp:
            return False

        stop_server(proc)
        proc = start_server(work_dir, "server.py", str(port))
        if not wait_for_port(port, timeout=10):
            return False
        resp = tcp_send("127.0.0.1", port, "GET baz\n")
        if "qux" not in resp:
            return False

        stop_server(proc)
        return run_pytest(work_dir)
    except Exception:
        return False
    finally:
        stop_server(proc)


# ---- Case 21: Job queue with workers ----

def _case21_setup(work_dir: Path) -> None:
    pass

def _case21_verify(work_dir: Path, response: str) -> bool:
    worker = start_server(work_dir, "worker.py")
    time.sleep(1)

    try:
        r = run_python(work_dir, "cli.py", "submit", "echo hello")
        if r.returncode != 0:
            return False
        job_id = r.stdout.strip().split()[-1]

        for _ in range(20):
            r = run_python(work_dir, "cli.py", "status", job_id)
            if r.returncode != 0:
                return False
            if "completed" in r.stdout.lower() or "done" in r.stdout.lower():
                break
            time.sleep(0.5)
        else:
            return False

        r = run_python(work_dir, "cli.py", "result", job_id)
        if r.returncode != 0 or "hello" not in r.stdout:
            return False

        r = run_python(work_dir, "cli.py", "submit", "exit 1")
        if r.returncode != 0:
            return False
        fail_id = r.stdout.strip().split()[-1]
        for _ in range(20):
            r = run_python(work_dir, "cli.py", "status", fail_id)
            if "failed" in r.stdout.lower() or "error" in r.stdout.lower():
                break
            time.sleep(0.5)
        else:
            return False

        r = run_python(work_dir, "cli.py", "list")
        if r.returncode != 0:
            return False

        stop_server(worker)
        return run_pytest(work_dir)
    except Exception:
        return False
    finally:
        stop_server(worker)


# ---- Case 22: File sync tool ----

def _case22_setup(work_dir: Path) -> None:
    pass

def _case22_verify(work_dir: Path, response: str) -> bool:
    src = work_dir / "test_src"
    dst = work_dir / "test_dst"
    src.mkdir(parents=True)
    (src / "a.txt").write_text("hello")
    sub = src / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world")
    deep = sub / "deep"
    deep.mkdir()
    (deep / "c.txt").write_text("nested")

    r = run_python(work_dir, "cli.py", str(src), str(dst))
    if r.returncode != 0:
        return False
    if not (dst / "a.txt").exists() or not (dst / "sub" / "b.txt").exists():
        return False
    if not (dst / "sub" / "deep" / "c.txt").exists():
        return False
    if (dst / "a.txt").read_text() != "hello":
        return False

    (src / "a.txt").write_text("modified")
    os.utime(src / "a.txt")
    r = run_python(work_dir, "cli.py", str(src), str(dst))
    if r.returncode != 0:
        return False
    if (dst / "a.txt").read_text() != "modified":
        return False

    (src / "sub" / "b.txt").unlink()
    r = run_python(work_dir, "cli.py", str(src), str(dst))
    if r.returncode != 0:
        return False
    if (dst / "sub" / "b.txt").exists():
        return False

    (src / "new.txt").write_text("new file")
    r = run_python(work_dir, "cli.py", str(src), str(dst), "--dry-run")
    if r.returncode != 0:
        return False
    if (dst / "new.txt").exists():
        return False

    return run_pytest(work_dir)


# ---- Case 23: Plugin system ----

def _case23_setup(work_dir: Path) -> None:
    pass

def _case23_verify(work_dir: Path, response: str) -> bool:
    input_file = work_dir / "test_input.txt"
    input_file.write_text("<b>Hello</b> <i>World</i>")

    r = run_python(work_dir, "cli.py", str(input_file))
    if r.returncode != 0:
        return False
    output = r.stdout

    if "<b>" in output or "<i>" in output:
        return False

    plugins_dir = work_dir / "plugins"
    if not plugins_dir.exists():
        return False

    (plugins_dir / "reverse.py").write_text(textwrap.dedent("""\
        from processor import Plugin

        class ReversePlugin(Plugin):
            def process(self, text):
                return text[::-1]
    """))

    r = run_python(work_dir, "cli.py", str(input_file))
    if r.returncode != 0:
        return False

    if (plugins_dir / "uppercase.py").exists():
        (plugins_dir / "uppercase.py").unlink()
        r = run_python(work_dir, "cli.py", str(input_file))
        if r.returncode != 0:
            return False

    return run_pytest(work_dir)


# ---- Case 24: Chat room server ----

def _case24_setup(work_dir: Path) -> None:
    pass

def _case24_verify(work_dir: Path, response: str) -> bool:
    import threading

    port = find_free_port()
    proc = start_server(work_dir, "server.py", str(port))
    if not wait_for_port(port, timeout=10):
        stop_server(proc)
        return False

    try:
        received_b = []

        def listen(sock, output_list):
            sock.settimeout(5)
            try:
                while True:
                    data = sock.recv(4096)
                    if not data:
                        break
                    output_list.append(data.decode())
            except (socket.timeout, OSError):
                pass

        sock_a = socket.create_connection(("127.0.0.1", port), timeout=5)
        time.sleep(0.3)

        sock_b = socket.create_connection(("127.0.0.1", port), timeout=5)
        listener = threading.Thread(target=listen, args=(sock_b, received_b))
        listener.daemon = True
        listener.start()
        time.sleep(0.3)

        sock_a.sendall(b"hello\n")
        time.sleep(0.5)

        sock_a.sendall(b"/nick Alice\n")
        time.sleep(0.3)
        sock_a.sendall(b"hi from alice\n")
        time.sleep(0.5)

        all_received = "".join(received_b)
        if "hello" not in all_received:
            sock_a.close()
            sock_b.close()
            return False

        if "alice" not in all_received.lower() and "Alice" not in all_received:
            sock_a.close()
            sock_b.close()
            return False

        sock_a.close()
        sock_b.close()
        time.sleep(0.5)

        log_file = work_dir / "chat.log"
        if log_file.exists():
            log_content = log_file.read_text()
            if "hello" not in log_content:
                return False

        stop_server(proc)
        return run_pytest(work_dir)
    except Exception:
        return False
    finally:
        stop_server(proc)


# ---- Case 25: Database-backed CRUD app ----

def _case25_setup(work_dir: Path) -> None:
    pass

def _case25_verify(work_dir: Path, response: str) -> bool:
    r = run_python(work_dir, "cli.py", "add",
        "--name", "Alice", "--email", "alice@test.com",
        "--phone", "555-0001", "--tags", "work,friend")
    if r.returncode != 0:
        r = run_python(work_dir, "cli.py", "add",
            "Alice", "alice@test.com", "555-0001", "work,friend")
        if r.returncode != 0:
            return False

    r = run_python(work_dir, "cli.py", "add",
        "--name", "Bob", "--email", "bob@test.com",
        "--phone", "555-0002", "--tags", "work")
    if r.returncode != 0:
        r = run_python(work_dir, "cli.py", "add",
            "Bob", "bob@test.com", "555-0002", "work")
        if r.returncode != 0:
            return False

    r = run_python(work_dir, "cli.py", "add",
        "--name", "Carol", "--email", "carol@test.com",
        "--phone", "555-0003", "--tags", "friend")
    if r.returncode != 0:
        r = run_python(work_dir, "cli.py", "add",
            "Carol", "carol@test.com", "555-0003", "friend")
        if r.returncode != 0:
            return False

    r = run_python(work_dir, "cli.py", "search", "alice")
    if r.returncode != 0 or "Alice" not in r.stdout:
        return False

    r = run_python(work_dir, "cli.py", "list", "--tag", "work")
    if r.returncode != 0:
        return False
    if "Alice" not in r.stdout or "Bob" not in r.stdout:
        return False
    if "Carol" in r.stdout:
        return False

    r = run_python(work_dir, "cli.py", "edit", "1", "--email", "new@test.com")
    if r.returncode != 0:
        return False
    r = run_python(work_dir, "cli.py", "show", "1")
    if r.returncode != 0 or "new@test.com" not in r.stdout:
        return False

    r = run_python(work_dir, "cli.py", "delete", "2")
    if r.returncode != 0:
        return False
    r = run_python(work_dir, "cli.py", "list")
    if r.returncode != 0 or "Bob" in r.stdout:
        return False

    r = run_python(work_dir, "cli.py", "export", "--format", "csv")
    if r.returncode != 0:
        return False
    csv_files = list(work_dir.glob("*.csv"))
    if csv_files:
        content = csv_files[0].read_text()
        if "Alice" not in content:
            return False

    r = run_python(work_dir, "cli.py", "export", "--format", "json")
    if r.returncode != 0:
        return False
    json_files = [f for f in work_dir.glob("*.json")
                  if f.name != ".local-chat-llm-permissions"]
    if json_files:
        try:
            json.loads(json_files[0].read_text())
        except json.JSONDecodeError:
            return False

    r = run_python(work_dir, "cli.py", "show", "999")
    if r.returncode == 0:
        if "error" not in r.stdout.lower() and "not found" not in r.stdout.lower():
            return False

    return run_pytest(work_dir)


# ---- Case registry ----

E2E_CASES = [
    {"name": "CLI tool", "level": 5, "task": "Create a Python CLI tool called `taskman.py` that manages a TODO list stored in `tasks.json`. It should support these commands via argparse: `add <task>` (adds a task), `list` (shows all tasks with IDs), `done <id>` (marks a task as done), and `clear` (removes all tasks). Include `test_taskman.py` with tests and make sure they pass.", "setup": _case10_setup, "verify": _case10_verify},
    {"name": "Multi-module project", "level": 5, "task": "Create a URL shortener with three modules: `shortener.py` (generates short codes from URLs using hashlib), `storage.py` (in-memory dict with `save(path)` and `load(path)` methods for JSON persistence), and `cli.py` (argparse CLI with `shorten <url>` and `resolve <code>` commands). Include tests and make sure they pass.", "setup": _case11_setup, "verify": _case11_verify},
    {"name": "REST API with persistence", "level": 6, "task": "Build a REST API using Python's `http.server` module with these endpoints: `POST /notes` (create a note with title and body, returns JSON with id), `GET /notes` (list all notes), `GET /notes/<id>` (get one note), `DELETE /notes/<id>` (delete a note). Store notes in a JSON file. The server should accept a port number as its first command line argument. Include tests that exercise all endpoints and make sure they pass.", "setup": _case12_setup, "verify": _case12_verify},
    {"name": "Multi-step data pipeline", "level": 6, "task": "Build a data processing pipeline with three scripts: `generate.py` creates a CSV file with 100 rows of fake user data (name, email, age, city), `transform.py` reads the CSV and outputs a JSON file grouped by city with user counts and average age per city, `report.py` reads the JSON and prints a formatted summary table. Include tests and make sure they pass.", "setup": _case13_setup, "verify": _case13_verify},
    {"name": "Configuration system", "level": 6, "task": "Build a configuration library with `config.py` that supports: loading from a YAML-like format (use `key: value` lines, one per line, `#` comments), environment variable overrides (`APP_<KEY>` overrides `key`), default values, and type coercion (int, float, bool, str). Include a CLI tool `config_tool.py` that can `get <key>`, `set <key> <value>`, and `list` all config. The config file is `app.conf` in the current directory. Include tests and make sure they pass.", "setup": _case14_setup, "verify": _case14_verify},
    {"name": "Fix a multi-file bug", "level": 7, "task": "This project has a bug. Users report that when they add items to their cart and then apply a discount code, the total is wrong. Find the bug, fix it, and add a test that would have caught it.", "setup": _case15_setup, "verify": _case15_verify},
    {"name": "Untangle spaghetti code", "level": 7, "task": "The file `analyzer.py` works but is a mess — one big function that does everything. Refactor it into clean, testable functions without changing its behavior. The existing `test_analyzer.py` must still pass after your changes. Add tests for the new functions you extract.", "setup": _case16_setup, "verify": _case16_verify},
    {"name": "Race condition fix", "level": 7, "task": "The file `counter.py` implements a thread-safe counter, but it has a race condition. The test in `test_counter.py` passes most of the time but occasionally fails. Find the race condition, fix it, and make the test reliable.", "setup": _case17_setup, "verify": _case17_verify},
    {"name": "Markdown to HTML converter", "level": 8, "task": "Build a Markdown to HTML converter in `markdown.py` that handles: headings (`#` through `###`), bold (`**text**`), italic (`*text*`), inline code (backtick-wrapped), code blocks (triple backtick), unordered lists (`- item`), links (`[text](url)`), and paragraphs (blank line separated). Include a CLI `md2html.py` that takes an input file and prints HTML to stdout. Include tests and make sure they pass.", "setup": _case18_setup, "verify": _case18_verify},
    {"name": "Log parser with pattern matching", "level": 8, "task": "Build a log analysis tool. `parser.py` parses log lines in the format `[YYYY-MM-DD HH:MM:SS] LEVEL: message` and extracts timestamp, level (INFO/WARN/ERROR), and message. `analyzer.py` takes a log file and produces: error count by hour, most frequent error messages (top 5), average time between consecutive errors, and any WARN that was followed by an ERROR within 60 seconds (potential escalations). `cli.py` takes a log file path and prints the analysis. Include tests and make sure they pass.", "setup": _case19_setup, "verify": _case19_verify},
    {"name": "Key-value store with TCP protocol", "level": 8, "task": "Build a TCP key-value store. `server.py` listens on a port (passed as first command line argument) and handles commands: `SET key value`, `GET key`, `DELETE key`, `KEYS` (list all keys). Use a simple text protocol — one command per line, responses are `OK value` or `ERROR message`. `client.py` provides a `KVClient` class that connects and exposes `set()`, `get()`, `delete()`, `keys()` methods. Data persists to a JSON file on disk. Include tests that start the server, run operations through the client, and verify correctness. Make sure tests pass.", "setup": _case20_setup, "verify": _case20_verify},
    {"name": "Job queue with workers", "level": 9, "task": "Build a file-based job queue system. `queue.py` provides a `JobQueue` class that can `submit(command)` (returns job ID), `status(job_id)` (returns pending/running/completed/failed), `result(job_id)` (returns stdout), and `list_jobs()`. `worker.py` is a long-running process that polls the queue directory, picks up pending jobs, executes them as shell commands, and writes results. `cli.py` provides commands: `submit <command>`, `status <id>`, `result <id>`, `list`. Jobs are stored as JSON files in a `jobs/` directory. Include tests and make sure they pass.", "setup": _case21_setup, "verify": _case21_verify},
    {"name": "File sync tool", "level": 9, "task": "Build a one-way file sync tool that mirrors a source directory to a destination directory. `sync.py` provides a `sync(src, dst)` function that: copies new files, updates modified files (compare by mtime and size), deletes files in dst that don't exist in src, handles nested subdirectories recursively, and returns a report of actions taken (copied, updated, deleted, unchanged). `cli.py` takes source and destination paths and prints the sync report. Include a `--dry-run` flag that shows what would happen without making changes. Include tests and make sure they pass.", "setup": _case22_setup, "verify": _case22_verify},
    {"name": "Plugin system", "level": 9, "task": "Build an extensible text processor with a plugin architecture. `processor.py` defines a `Plugin` base class with a `process(text) -> text` method and a `PluginManager` that discovers and loads plugins from a `plugins/` directory. `cli.py` takes input text (from a file path argument) and applies all loaded plugins in order. Create three example plugins in `plugins/`: `uppercase.py` (converts to uppercase), `strip_html.py` (removes HTML tags), and `word_count.py` (appends a word count line at the end). Plugins should be loaded automatically by filename — no registration needed. Include tests and make sure they pass.", "setup": _case23_setup, "verify": _case23_verify},
    {"name": "Chat room server", "level": 10, "task": "Build a multi-client chat room over TCP. `server.py` accepts multiple simultaneous connections using threading (port passed as first argument), broadcasts messages to all connected clients, supports commands `/nick <name>` (set nickname, default is 'anonymous'), `/who` (list connected users), `/quit` (disconnect). `client.py` provides a `ChatClient` class that connects, sends messages, and receives broadcasts in a background thread. Server logs all messages to `chat.log` with timestamps. Include tests that connect multiple clients, send messages, verify broadcasts, and test nick changes. Make sure tests pass.", "setup": _case24_setup, "verify": _case24_verify},
    {"name": "Database-backed CRUD app", "level": 10, "task": "Build a contact manager backed by SQLite. `db.py` handles database setup and provides functions: `add_contact(name, email, phone, tags)`, `get_contact(id)`, `search_contacts(query)` (searches name and email), `update_contact(id, **fields)`, `delete_contact(id)`, `list_contacts(tag=None)` (optionally filter by tag). `export.py` exports contacts to CSV or JSON (format chosen by flag). `cli.py` provides subcommands: `add`, `list`, `search <query>`, `show <id>`, `edit <id>`, `delete <id>`, `export --format csv|json`. Include tests covering all operations including edge cases (empty search, nonexistent ID). Make sure tests pass.", "setup": _case25_setup, "verify": _case25_verify},
]


@register
class E2EProjectSuite(BenchmarkSuite):
    name = "e2e_project"
    description = "End-to-end project creation — levels 5-10"

    async def run(self, client: AppClient, context_length: int, config: dict) -> SuiteResult:
        cases: list[CaseResult] = []
        runs_per_case = config.get("runs_per_case", 1)
        levels = config.get("levels")

        for case_def in E2E_CASES:
            if levels and case_def["level"] not in levels:
                continue
            runs: list[RunResult] = []

            for run_idx in range(runs_per_case):
                work_dir = _make_work_dir(case_def["name"], run_idx)
                base_setup(work_dir)
                case_def["setup"](work_dir)

                # Restart app from the test's working directory
                await client.stop()
                await client.start(cwd=work_dir)
                await client.send_command("/agent on")

                result = await client.send_prompt(case_def["task"])

                passed = case_def["verify"](work_dir, result.response_text)

                run_metrics = dict(result.metrics)
                self_verified = any(
                    entry.get("tool_name") == "run_command"
                    for entry in result.tool_log
                    if entry.get("type") == "call"
                )
                run_metrics["self_verified"] = self_verified

                runs.append(RunResult(
                    passed=passed,
                    metrics=run_metrics,
                    details={
                        "tool_log": result.tool_log,
                        "response_text": result.response_text,
                    },
                ))

            case_metrics = self._compute_case_metrics(runs)
            cases.append(CaseResult(
                name=case_def["name"],
                prompt=case_def["task"],
                metrics=case_metrics,
                runs=runs,
                details={"level": case_def["level"]},
            ))

        suite_metrics = self._compute_suite_metrics(cases)
        return SuiteResult(suite_name=self.name, metrics=suite_metrics, cases=cases)

    def _compute_case_metrics(self, runs: list[RunResult]) -> dict:
        if not runs:
            return {}
        metrics: dict = {}
        metrics["pass_rate"] = sum(1 for r in runs if r.passed) / len(runs)
        for key in ["iterations", "tool_calls", "tool_errors"]:
            vals = [r.metrics.get(key) for r in runs if r.metrics.get(key) is not None]
            if vals:
                metrics[f"avg_{key}"] = sum(vals) / len(vals)
        return metrics

    def _compute_suite_metrics(self, cases: list[CaseResult]) -> dict:
        if not cases:
            return {}
        total = len(cases)
        reliable = sum(1 for c in cases if c.pass_rate == 1.0) / total
        any_pass = sum(1 for c in cases if c.pass_rate > 0.0) / total
        return {
            "reliable_pass_rate": round(reliable, 2),
            "any_pass_rate": round(any_pass, 2),
        }
