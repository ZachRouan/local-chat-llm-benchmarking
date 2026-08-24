> Design document written before implementation (April 2026). The README describes current behavior; this records the original design and rationale.

# Advanced Agent Test Cases (Levels 6-10)

Extension to the benchmarking system adding 14 harder agent test cases across 5 new difficulty levels, pushing models on scale, debugging/reasoning, domain knowledge, system integration, and full application development.

## Overview

Levels 1-5 (11 cases) test basic tool use through project creation. Levels 6-10 (14 cases) escalate difficulty across three dimensions:
- **Scale** — More files, more interacting components
- **Debugging/reasoning** — Understanding broken or messy code before modifying it
- **Real-world complexity** — Protocols, formats, concurrency, persistence patterns

All levels use `max_iterations = 30` and clear requirements (no ambiguity testing). Consistent failure at higher levels is expected and is useful data.

## Verification Approach

Two layers of verification for all new cases:
1. **Functional testing** — The benchmark runs the output: starts servers, sends requests, checks responses, verifies persistence, exercises edge cases
2. **Model self-testing** — The model must write and pass its own tests. If the task says "include tests," the verify function checks that tests exist and pass via `python -m pytest`

## Cases

### Level 6: Multi-component projects (Scale)

2-3 interacting components that must work together.

**Case 12 — REST API with persistence**
- Task: "Build a REST API using Python's `http.server` module with these endpoints: `POST /notes` (create a note with title and body, returns JSON with id), `GET /notes` (list all notes), `GET /notes/<id>` (get one note), `DELETE /notes/<id>` (delete a note). Store notes in a JSON file. Include tests that exercise all endpoints and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Start server as subprocess on a random port
  2. POST to create 2 notes, check 201 status and JSON response with id
  3. GET /notes, check both notes returned
  4. GET /notes/<id>, check correct note returned
  5. DELETE /notes/<id>, check 200 status
  6. GET /notes, check only 1 note remains
  7. Stop server, restart it, GET /notes, check data persisted
  8. Model's pytest tests pass

**Case 13 — Multi-step data pipeline**
- Task: "Build a data processing pipeline with three scripts: `generate.py` creates a CSV file with 100 rows of fake user data (name, email, age, city), `transform.py` reads the CSV and outputs a JSON file grouped by city with user counts and average age per city, `report.py` reads the JSON and prints a formatted summary table. Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Run `generate.py`, check CSV exists with 100 data rows + header
  2. Run `transform.py`, check JSON is valid and has city groupings with count and avg_age
  3. Run `report.py`, check output contains city names and numeric values
  4. Pipeline is idempotent — run all three again, same structure
  5. Model's pytest tests pass

**Case 14 — Configuration system**
- Task: "Build a configuration library with `config.py` that supports: loading from a YAML-like format (use `key: value` lines, one per line, `#` comments), environment variable overrides (`APP_<KEY>` overrides `key`), default values, and type coercion (int, float, bool, str). Include a CLI tool `config_tool.py` that can `get <key>`, `set <key> <value>`, and `list` all config. Include tests and make sure they pass."
- Setup: Create a sample config file `app.conf` with `port: 8080`, `debug: true`, `name: myapp`, `# This is a comment`, `timeout: 30.5`
- Verify:
  1. `config_tool.py get port` returns "8080"
  2. `config_tool.py get debug` returns "true" or "True"
  3. `config_tool.py list` shows all keys
  4. `config_tool.py set port 9090` then `get port` returns "9090"
  5. Set env var `APP_PORT=3000`, run `config_tool.py get port`, returns "3000" (env override)
  6. Model's pytest tests pass

### Level 7: Debugging & reasoning (Complex bugs)

Model must understand existing code, find problems, and fix them correctly.

**Case 15 — Fix a multi-file bug**
- Task: "This project has a bug. Users report that when they add items to their cart and then apply a discount code, the total is wrong. Find the bug, fix it, and add a test that would have caught it."
- Setup: Create `cart.py` with a Cart class where `apply_discount` caches the total at discount time in `self._discounted_total` and `get_total` returns `self._discounted_total` if set — so items added after the discount are ignored. Create `discounts.py` with a lookup function. Create `test_cart.py` with tests that add items, apply discount, and check total — but never add items *after* applying a discount.
- Verify:
  1. Original tests still pass
  2. The specific bug scenario works: add item ($10), apply 20% discount, add another item ($5), total should be $13 (not $8)
  3. `cart.py` no longer caches a discounted total (or recalculates properly)
  4. Model's new test covers the add-after-discount scenario
  5. All tests pass

**Case 16 — Untangle spaghetti code**
- Task: "The file `analyzer.py` works but is a mess — one 120-line function that does everything. Refactor it into clean, testable functions without changing its behavior. The existing `test_analyzer.py` must still pass after your changes. Add tests for the new functions you extract."
- Setup: Create `analyzer.py` with a single `analyze(filepath)` function (~120 lines) that reads a text file, counts words, finds top 5 most common words, calculates average word length, finds longest and shortest sentences, and returns a dict with all stats. Create `test_analyzer.py` with integration tests. Create `sample.txt` with several paragraphs.
- Verify:
  1. Original `test_analyzer.py` passes unchanged
  2. `analyzer.py` has no function longer than 20 lines
  3. `analyzer.py` has at least 4 functions (the original extracted into helpers)
  4. Running `analyze("sample.txt")` produces identical results to a pre-computed expected dict
  5. Model's new tests pass
  6. All tests pass

**Case 17 — Race condition fix**
- Task: "The file `counter.py` implements a thread-safe counter, but it has a race condition. The test in `test_counter.py` passes most of the time but occasionally fails. Find the race condition, fix it, and make the test reliable."
- Setup: Create `counter.py` with a Counter class where `increment()` reads `self._value`, sleeps 0.001s, then writes `self._value + 1` (simulating a race window). Create `test_counter.py` that spawns 10 threads each incrementing 100 times, checks final value is 1000.
- Verify:
  1. Run `test_counter.py` 5 times in a row — all pass
  2. `counter.py` source contains `threading.Lock` or `threading.RLock` (or equivalent synchronization)
  3. The `time.sleep(0.001)` race simulation is removed or is inside a lock
  4. All tests pass

### Level 8: Real-world protocols & formats (Domain knowledge)

Tasks requiring understanding of specific formats, protocols, or patterns.

**Case 18 — Markdown to HTML converter**
- Task: "Build a Markdown to HTML converter in `markdown.py` that handles: headings (`#` through `###`), bold (`**text**`), italic (`*text*`), inline code (`` `code` ``), code blocks (triple backtick), unordered lists (`- item`), links (`[text](url)`), and paragraphs (blank line separated). Include a CLI `md2html.py` that takes an input file and prints HTML to stdout. Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Create a test markdown file with all 8 supported elements
  2. Run `md2html.py test.md`, capture output
  3. Output contains `<h1>`, `<h2>`, `<h3>` tags
  4. Output contains `<strong>` and `<em>` tags
  5. Output contains `<code>` and `<pre>` tags
  6. Output contains `<ul>` and `<li>` tags
  7. Output contains `<a href="...">` tags
  8. Output contains `<p>` tags for paragraphs
  9. Nested formatting works (bold inside list item)
  10. Model's pytest tests pass

**Case 19 — Log parser with pattern matching**
- Task: "Build a log analysis tool. `parser.py` parses log lines in the format `[YYYY-MM-DD HH:MM:SS] LEVEL: message` and extracts timestamp, level (INFO/WARN/ERROR), and message. `analyzer.py` takes a log file and produces: error count by hour, most frequent error messages (top 5), average time between consecutive errors, and any WARN that was followed by an ERROR within 60 seconds (potential escalations). `cli.py` takes a log file path and prints the analysis. Include tests and make sure they pass."
- Setup: Create `sample.log` with ~50 lines across several hours, including: multiple INFOs, repeated ERROR messages, a WARN followed by an ERROR 30 seconds later (escalation), and a WARN followed by an ERROR 90 seconds later (not an escalation).
- Verify:
  1. Run `cli.py sample.log`, capture output
  2. Output contains error count per hour (check at least one hour's count matches expected)
  3. Output contains top error messages
  4. Output contains average time between errors
  5. Output identifies the 30-second escalation but not the 90-second one
  6. Model's pytest tests pass

**Case 20 — Key-value store with TCP protocol**
- Task: "Build a TCP key-value store. `server.py` listens on a port and handles commands: `SET key value`, `GET key`, `DELETE key`, `KEYS` (list all keys). Use a simple text protocol — one command per line, responses are `OK value` or `ERROR message`. `client.py` provides a `KVClient` class that connects and exposes `set()`, `get()`, `delete()`, `keys()` methods. Data persists to a JSON file on disk. Include tests that start the server, run operations through the client, and verify correctness. Make sure tests pass."
- Setup: Empty working dir
- Verify:
  1. Start `server.py` on a random available port as subprocess
  2. Use `KVClient` to SET "foo" = "bar"
  3. GET "foo", verify returns "bar"
  4. SET "baz" = "qux", KEYS returns both keys
  5. DELETE "foo", GET "foo" returns error, KEYS returns only "baz"
  6. Stop server, restart it on same port, GET "baz" returns "qux" (persistence)
  7. Model's pytest tests pass

### Level 9: System integration (Multiple coordinating components)

Components that must coordinate, handle errors, and maintain state across interactions.

**Case 21 — Job queue with workers**
- Task: "Build a file-based job queue system. `queue.py` provides a `JobQueue` class that can `submit(command)` (returns job ID), `status(job_id)` (returns pending/running/completed/failed), `result(job_id)` (returns stdout), and `list_jobs()`. `worker.py` is a long-running process that polls the queue directory, picks up pending jobs, executes them as shell commands, and writes results. `cli.py` provides commands: `submit <command>`, `status <id>`, `result <id>`, `list`. Jobs are stored as JSON files in a `jobs/` directory. Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Start `worker.py` as background subprocess
  2. Use `cli.py submit "echo hello"`, capture job ID
  3. Poll `cli.py status <id>` until completed (timeout 10s)
  4. `cli.py result <id>` contains "hello"
  5. `cli.py submit "exit 1"`, wait, verify status is "failed"
  6. `cli.py submit "echo a"`, `cli.py submit "echo b"`, `cli.py submit "echo c"`, `cli.py list` shows all 5 jobs
  7. Stop worker, verify no orphaned processes
  8. Model's pytest tests pass

**Case 22 — File sync tool**
- Task: "Build a one-way file sync tool that mirrors a source directory to a destination directory. `sync.py` provides a `sync(src, dst)` function that: copies new files, updates modified files (compare by mtime and size), deletes files in dst that don't exist in src, handles nested subdirectories recursively, and returns a report of actions taken (copied, updated, deleted, unchanged). `cli.py` takes source and destination paths and prints the sync report. Include a `--dry-run` flag that shows what would happen without making changes. Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Create source dir with nested files (`src/a.txt`, `src/sub/b.txt`, `src/sub/deep/c.txt`)
  2. Run `cli.py src dst`, verify all files copied to dst with correct structure
  3. Modify `src/a.txt`, run sync again, verify only `a.txt` updated in report
  4. Delete `src/sub/b.txt`, run sync, verify `dst/sub/b.txt` deleted
  5. Run `cli.py src dst --dry-run`, modify source, verify dst unchanged after dry-run
  6. Model's pytest tests pass

**Case 23 — Plugin system**
- Task: "Build an extensible text processor with a plugin architecture. `processor.py` defines a `Plugin` base class with a `process(text) -> text` method and a `PluginManager` that discovers and loads plugins from a `plugins/` directory. `cli.py` takes input text (from stdin or a file) and applies all loaded plugins in order. Create three example plugins in `plugins/`: `uppercase.py` (converts to uppercase), `strip_html.py` (removes HTML tags), and `word_count.py` (appends a word count line at the end). Plugins should be loaded automatically by filename — no registration needed. Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. Create input file with HTML content: `<b>Hello</b> <i>World</i>`
  2. Run `cli.py input.txt`, verify output is uppercase, HTML stripped, has word count
  3. Create a new plugin `plugins/reverse.py` that reverses text (without modifying any existing code)
  4. Run `cli.py input.txt` again, verify the new plugin is applied
  5. Remove `plugins/uppercase.py`, run again, verify output is no longer uppercased
  6. Model's pytest tests pass

### Level 10: Full application (Everything combined)

Complete working applications with multiple modules, error handling, persistence, concurrency, and comprehensive testing.

**Case 24 — Chat room server**
- Task: "Build a multi-client chat room over TCP. `server.py` accepts multiple simultaneous connections using threading, broadcasts messages to all connected clients, supports commands `/nick <name>` (set nickname, default is 'anonymous'), `/who` (list connected users), `/quit` (disconnect). `client.py` provides a `ChatClient` class that connects, sends messages, and receives broadcasts in a background thread. `cli_client.py` is a terminal client that uses `ChatClient` — one thread reads stdin and sends, another prints incoming messages. Server logs all messages to `chat.log` with timestamps. Include tests that connect multiple clients, send messages, verify broadcasts, and test nick changes. Make sure tests pass."
- Setup: Empty working dir
- Verify:
  1. Start `server.py` on a random port as subprocess
  2. Connect Client A and Client B using `ChatClient`
  3. Client A sends "hello", verify Client B receives it
  4. Client A runs `/nick Alice`, sends "hi", verify Client B sees "Alice: hi"
  5. Client B runs `/who`, verify output lists both nicks
  6. Client A disconnects, verify Client B gets a leave notification
  7. Check `chat.log` exists and contains message entries with timestamps
  8. Model's pytest tests pass

**Case 25 — Database-backed CRUD app**
- Task: "Build a contact manager backed by SQLite. `db.py` handles database setup and provides functions: `add_contact(name, email, phone, tags)`, `get_contact(id)`, `search_contacts(query)` (searches name and email), `update_contact(id, **fields)`, `delete_contact(id)`, `list_contacts(tag=None)` (optionally filter by tag). `export.py` exports contacts to CSV or JSON (format chosen by flag). `cli.py` provides subcommands: `add`, `list`, `search <query>`, `show <id>`, `edit <id>`, `delete <id>`, `export --format csv|json`. Include tests covering all operations including edge cases (duplicate emails, empty search, nonexistent ID). Make sure tests pass."
- Setup: Empty working dir
- Verify:
  1. `cli.py add --name "Alice" --email "alice@test.com" --phone "555-0001" --tags "work,friend"` exits 0
  2. `cli.py add --name "Bob" --email "bob@test.com" --phone "555-0002" --tags "work"` exits 0
  3. `cli.py add --name "Carol" --email "carol@test.com" --phone "555-0003" --tags "friend"` exits 0
  4. `cli.py search alice` output contains "Alice"
  5. `cli.py list --tag work` shows Alice and Bob but not Carol
  6. `cli.py edit 1 --email "new@test.com"` then `cli.py show 1` shows updated email
  7. `cli.py delete 2` then `cli.py list` shows only Alice and Carol
  8. `cli.py export --format csv` produces valid CSV with correct data
  9. `cli.py export --format json` produces valid JSON with correct data
  10. `cli.py show 999` exits with error message (not a crash)
  11. Model's pytest tests pass

## Implementation

- All new levels use `max_iterations = 30`
- New cases are added to `E2E_CASES` list in `e2e_project.py` with their setup/verify functions
- Level 7 cases (debugging) have non-empty setup functions that create broken or messy codebases
- Levels 8-10 verify functions that need servers use helper functions for starting/stopping subprocesses and finding available ports
- `test-programs/` directories use the same naming convention (`rest-api-with-persistence/`, `chat-room-server/`, etc.)
- Helper utilities for functional verification (HTTP requests, TCP connections, subprocess management) go in a new `benchmarks/suites/verify_helpers.py` module
