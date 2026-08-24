> Design document written before implementation (April 2026). The README describes current behavior; this records the original design and rationale.

# Benchmarking System Design

A standalone CLI tool for benchmarking llama-chat — measuring inference performance, agent efficiency, and regression detection across models and configurations.

## Goals

1. **Performance profiling** — Measure throughput (tok/s), time to first token (TTFT), and latency under different conditions (context lengths, multi-turn, tool use)
2. **Regression detection** — Detect when a model swap, quantization change, or config change degrades performance by comparing against previous runs
3. **Model comparison** — Accumulate results over time to compare different models on the same tasks

## Architecture

```
llama-chat-benchmarking/
├── benchmark.py              # CLI entry point
├── benchmarks/
│   ├── __init__.py
│   ├── parser.py             # Stats line and tool output regex parsers
│   ├── runner.py             # AppClient — subprocess wrapper, byte-by-byte stdout reader
│   ├── results.py            # JSON storage, loading, delta comparison
│   ├── report.py             # Rich terminal tables + delta display
│   └── suites/
│       ├── __init__.py       # Suite registry + @register decorator
│       ├── base.py           # BenchmarkSuite, SuiteResult, CaseResult, RunResult
│       ├── speed.py          # Short Q&A throughput
│       ├── generation.py     # Long-form generation throughput
│       ├── code.py           # Code generation + syntax validation
│       ├── context.py        # Context window scaling behavior
│       ├── multiturn.py      # Multi-turn conversation simulation
│       ├── agent.py          # Tool use test cases (levels 1-4)
│       └── e2e_project.py    # Full project creation (level 5)
├── tests/                    # pytest test suite
├── test-programs/            # Agent/E2E working directories (gitignored, inspectable)
├── results/                  # JSON result files (gitignored)
└── requirements.txt
```

The benchmarking tool lives in its own repo, fully decoupled from llama-chat. It drives the chat app as a subprocess — no imports, no shared code. This means the benchmark always tests the real app exactly as a user experiences it.

## CLI Interface

```bash
# Run all suites against a server
python benchmark.py --server localhost:8082

# Run specific suites
python benchmark.py --server localhost:8082 --suite speed,agent

# Compare against last run for this model
python benchmark.py --server localhost:8082 --compare

# List available suites
python benchmark.py --list

# Show results from a previous run
python benchmark.py --results results/2026-04-13-1430-gemma-4-27b.json

# Tag a run
python benchmark.py --server localhost:8082 --label "Q4_K_M quant"
```

**Arguments:**
- `--server` — Required. `host:port` of the llama.cpp server.
- `--suite` — Comma-separated suite names. Defaults to all.
- `--compare` — After running, load the most recent previous result for the same model and show deltas.
- `--list` — List available suites and exit.
- `--results` — Display results from a JSON file without running anything.
- `--label` — Tag the run with a label (e.g., quant type, GPU config).
- `--temperature` — Override temperature (default: from chat app config).
- `--max-tokens` — Override max tokens (default: from chat app config).
- `--runs N` — Repeat each test case N times. Reports pass rate per case (e.g., 2/3) instead of binary pass/fail. Default: 1.

## Subprocess Communication

### App Discovery

The benchmark resolves the `llama-chat` symlink from PATH to find the app's project directory, Python interpreter (`.venv/bin/python`), and `main.py`. It launches the app directly with `python -u main.py` (unbuffered) rather than through the bash wrapper, since the wrapper introduces buffering issues with piped stdin/stdout.

### Startup Sequence

1. Launch `python -u main.py` with `LLAMA_SERVERS` and `PYTHONUNBUFFERED=1` env vars
2. Read stdout byte-by-byte (since `input()` prompts don't end with newlines)
3. If session resume prompt appears ("Resume previous session?"), send "n"
4. Wait for model selection menu, send the first selectable choice number
5. Wait for the banner (extract model name and context length) and `You > ` prompt

### During Benchmarks

1. Write prompt to stdin, start timer
2. Read stdout byte-by-byte, accumulating into lines
3. Record time of first non-empty output (TTFT)
4. Continue reading until the stats line appears (regex: `\d+ tokens in .* tok/s`)
5. Parse metrics from the stats line
6. For agent suites, also capture tool call lines (`→ tool_name:`) and result lines (`✓` / `✗`)
7. Wait for the next `You > ` or `Agent > ` prompt — ready for next case

### Between Prompts

All suites send `/clear` between prompts so each case starts with a clean context window. Agent/E2E suites restart the app entirely per case (since each case needs a different working directory).

### Cleanup

Send `/quit` to exit cleanly.

### Error Handling

Timeout if no output appears within 180 seconds. If the process exits unexpectedly, capture stderr and report it as a suite failure.

## Metrics

### Core Metrics (all suites)

| Metric | Source | Description |
|--------|--------|-------------|
| `ttft_ms` | External timer | Time from prompt sent to first output on stdout |
| `tok_s` | Stats line | Tokens per second (generation throughput) |
| `total_tokens` | Stats line | Completion token count |
| `duration_s` | Stats line | Wall clock time for generation |
| `context_used` | Stats line | Prompt + completion tokens |
| `context_pct` | Stats line | Context usage as percentage of context window |

The stats line is already printed by the chat app after every response:
```
1653 tokens in 73.0s (22.7 tok/s) · context: 1,676/100,096 (2%)
```

These values come from server-reported `usage` fields in the SSE stream (completion_tokens, prompt_tokens) and `time.monotonic()` timing between first and last token. They are accurate, not estimates.

### Agent-Specific Metrics (agent + e2e suites)

| Metric | Source | Description |
|--------|--------|-------------|
| `iterations` | Count of stats lines per prompt | Number of tool loop iterations |
| `tool_calls` | Count of `→` lines | Total tool calls made |
| `tool_errors` | Count of `✗` lines | Tool calls that returned errors |
| `self_verified` | Presence of verification patterns | Did the model verify its work |
| `passed` | Suite-defined validation | Did the output meet success criteria |

## Suite Base Class

```python
class BenchmarkSuite:
    name: str           # e.g., "speed"
    description: str    # e.g., "Short Q&A throughput"

    async def run(self, client: AppClient, context_length: int, config: dict) -> SuiteResult
```

`AppClient` is a class defined in `runner.py` that wraps the subprocess. It resolves `llama-chat` from PATH to find the app's Python and `main.py`, and reads stdout byte-by-byte to handle `input()` prompts that don't end with newlines. Methods:
- `start(cwd=None)` — Launch the app from the given directory, handle model selection and session resume
- `send_prompt(text) -> PromptResult` — Write prompt to stdin, parse stdout until `You > ` returns, extract metrics from stats line and tool call output
- `send_command(text)` — Send a slash command (e.g., `/clear`, `/agent on`) and wait for the prompt to return
- `stop()` — Send `/quit` and wait for process exit

### SuiteResult

```python
@dataclass
class SuiteResult:
    suite_name: str
    metrics: dict       # Aggregated metrics (e.g., avg_tok_s, avg_ttft_ms)
    cases: list[CaseResult]

@dataclass
class CaseResult:
    name: str           # Human-readable case name
    prompt: str         # The prompt sent (or a summary)
    metrics: dict       # Per-case metrics (tok_s, ttft_ms, etc.)
    runs: list[RunResult]  # One per --runs N iteration
    details: dict       # Optional — tool call log, iteration count, etc.

@dataclass
class RunResult:
    passed: bool        # Did this run pass verification
    metrics: dict       # Per-run metrics
    details: dict       # Tool call log, iteration count, etc.
```

### Multi-Run Behavior (`--runs N`)

When `--runs N` is greater than 1, each test case is executed N times independently. Each run gets a fresh subprocess state (`/clear` between runs). For agent/e2e cases, each run gets its own directory (e.g., `cli-tool/`, `cli-tool-run2/`, `cli-tool-run3/`).

Per-case metrics are averaged across runs. Pass rate is reported as `k/N` (e.g., `2/3`).

Aggregated suite metrics include:
- `reliable_pass_rate` — Fraction of cases that passed all N runs
- `any_pass_rate` — Fraction of cases that passed at least one run

## Suites

### Speed

5-10 short factual prompts ("What is the capital of France?", "Explain what a hash table is in two sentences"). Single-turn, no tools. Measures pure TTFT and tok/s. Fast baseline.

### Generation

2-3 prompts requesting long-form output ("Write a detailed essay about the history of computing"). Measures sustained tok/s over longer generations. Tests whether throughput degrades as the response grows.

### Code

3-5 prompts asking for self-contained functions ("Write a Python function that finds the longest palindromic substring"). Scored on: does it parse (syntax check via `ast.parse`), does it look reasonable (basic structural checks), plus speed metrics.

### Context

Sends progressively longer prompts or multiple turns to naturally fill the context window (targeting ~10%, 25%, 50%, 75%, 90% usage). Measures how TTFT and tok/s change as context grows. Produces a degradation curve.

### Multi-turn

Simulates a 5-10 message conversation with back-and-forth exchanges. Measures per-turn metrics to detect if performance degrades over the conversation as context accumulates.

### Agent & E2E Test Cases

The agent and e2e suites share 11 test cases across 5 difficulty levels. All run in agent mode (`/agent on`). Each case has:
- **Setup function** — Creates files/directories in a named working directory under `test-programs/`
- **Task string** — The prompt sent to the model
- **Verify function** — A Python callable `verify(work_dir: Path) -> bool` that performs strict validation (file contents, subprocess exit codes, import checks)

Each run gets its own directory (e.g., `test-programs/read-and-answer/`, `test-programs/cli-tool-run2/`). Files are kept after runs so you can inspect what the model produced. The app is restarted per case with `client.start(cwd=work_dir)` so all tool operations (read_file, write_file, etc.) operate relative to the test directory.

#### Base Setup (all agent/e2e cases)

Before each case's own setup runs, a shared base setup writes a permissive permissions file to the temp directory. This prevents the chat app's permission system from prompting for confirmation on every tool call during benchmarks:

```python
permissions = {
    "read_file": "allow",
    "list_directory": "allow",
    "search_files": "allow",
    "write_file": "allow",
    "run_command": "allow",
    "allow_rules": []
}
Path(work_dir / ".llama-chat-permissions").write_text(json.dumps(permissions))
```

No changes to the chat app itself. The benchmark creates the right environment, same as a user would if they wanted to skip prompts in a project directory.

#### Level 1: Trivial (single tool call)

**Case 1 — Read and answer**
- Task: "Read the file `info.txt` and tell me what the author's name is."
- Setup: Create `info.txt` containing `Title: My Project\nAuthor: Alice Chen\nVersion: 1.0`
- Verify: Response text contains "Alice Chen"

**Case 2 — Create a file**
- Task: "Create a file called `greeting.txt` that contains exactly the text 'Hello, World!'"
- Setup: Empty working dir
- Verify: `greeting.txt` exists, contents strip to `Hello, World!`

#### Level 2: Easy (2-3 tool calls)

**Case 3 — List and count**
- Task: "How many Python files are in the `src/` directory?"
- Setup: Create `src/` with 5 `.py` files (`a.py` through `e.py`) and 3 `.txt` files
- Verify: Response contains "5"

**Case 4 — Search and report**
- Task: "Find all TODO comments in this project and list them with their file paths."
- Setup: Create 4 files. `app.py` has `# TODO: add logging`. `utils.py` has `# TODO: handle edge case`. `config.py` has `todo_message = "TODO items go here"` (string, not a comment — the interesting edge case). `readme.md` has no TODOs.
- Verify: Response contains both actual TODO comments with correct file paths (`app.py`, `utils.py`). Does not claim `readme.md` has TODOs.

#### Level 3: Medium (multiple tools, reasoning)

**Case 5 — Read, modify, write**
- Task: "The file `config.json` has the port set to 3000. Change it to 8080."
- Setup: Create `config.json` with `{"host": "localhost", "port": 3000, "debug": true}`
- Verify: `config.json` is valid JSON. `port` is `8080`. `host` is still `"localhost"`. `debug` is still `true`.

**Case 6 — Multi-file creation**
- Task: "Create a Python package called `mathutils` with an `__init__.py` that imports from `operations.py`. `operations.py` should have functions `add(a, b)` and `multiply(a, b)` that return their results."
- Setup: Empty working dir
- Verify: `mathutils/__init__.py` and `mathutils/operations.py` exist. Running `python -c "from mathutils.operations import add, multiply; assert add(2,3)==5; assert multiply(2,3)==6"` in the working dir succeeds.

**Case 7 — Debug a broken script**
- Task: "The script `app.py` has a bug. Fix it so it runs without errors."
- Setup: Create `app.py` with a function that uses an undefined variable (e.g., `result = count * multiplier` where `multiplier` should be `factor`, and `factor` is defined above)
- Verify: `python app.py` exits with code 0 and produces expected output.

#### Level 4: Hard (planning + self-verification expected)

**Case 8 — Create project with tests**
- Task: "Create a Python module `stringutils.py` with functions `reverse(s)`, `is_palindrome(s)`, and `word_count(s)`. Then create `test_stringutils.py` with pytest tests for each function. Run the tests and make sure they pass."
- Setup: Empty working dir
- Verify: Both files exist. `python -m pytest test_stringutils.py -v` passes (exit code 0). Test file contains at least 3 test functions.
- Scoring bonus: `self_verified = True` if tool log shows the model ran pytest itself before finishing.

**Case 9 — Refactor across files**
- Task: "The function `calculate_total` is duplicated in both `orders.py` and `invoices.py`. Extract it into a shared `utils.py` module, update both files to import from there, and verify nothing is broken."
- Setup: Create `orders.py` and `invoices.py`, each with an identical `calculate_total(items)` function and a `main()` that calls it and prints the result. Both scripts should work standalone (`python orders.py` prints a number).
- Verify: `utils.py` exists and contains `calculate_total`. Neither `orders.py` nor `invoices.py` defines `calculate_total` locally. Both contain `from utils import calculate_total`. `python orders.py` and `python invoices.py` both exit with code 0 and produce correct output.

#### Level 5: Expert (full project creation)

Level 5 cases use `max_iterations = 20` (vs the default 15). Consistent failure (0/N) on these cases is expected for smaller models and is useful data, not a test bug.

**Case 10 — CLI tool**
- Task: "Create a Python CLI tool called `taskman.py` that manages a TODO list stored in `tasks.json`. It should support these commands via argparse: `add <task>` (adds a task), `list` (shows all tasks with IDs), `done <id>` (marks a task as done), and `clear` (removes all tasks). Include `test_taskman.py` with tests and make sure they pass."
- Setup: Empty working dir
- Verify: Sequential commands work correctly:
  1. `python taskman.py add "Buy milk"` — exits 0
  2. `python taskman.py add "Write tests"` — exits 0
  3. `python taskman.py list` — output contains both tasks with IDs
  4. `python taskman.py done 1` — exits 0
  5. `python taskman.py list` — shows task 1 as done
  6. `python taskman.py clear` — exits 0
  7. `python taskman.py list` — shows no tasks or empty
  8. `tasks.json` is valid JSON at each step
  9. `python -m pytest test_taskman.py` passes

**Case 11 — Multi-module project**
- Task: "Create a URL shortener with three modules: `shortener.py` (generates short codes from URLs using hashlib), `storage.py` (in-memory dict with `save(path)` and `load(path)` methods for JSON persistence), and `cli.py` (argparse CLI with `shorten <url>` and `resolve <code>` commands). Include tests and make sure they pass."
- Setup: Empty working dir
- Verify:
  1. All three module files exist
  2. `python cli.py shorten https://example.com` — exits 0, prints a short code
  3. Capture that code, run `python cli.py resolve <code>` — output contains `https://example.com`
  4. `python -m pytest` passes if test files exist

## Results Storage

### File Format

Each run produces a JSON file in `results/`, named `YYYY-MM-DD-HHMM-<model-name>.json`:

```json
{
  "timestamp": "2026-04-13T14:30:00Z",
  "model": "gemma-4-27b-it-Q4_K_M",
  "server": "localhost:8082",
  "context_length": 131072,
  "label": "Q4_K_M quant",
  "runs_per_case": 3,
  "suites": {
    "speed": {
      "metrics": {"avg_tok_s": 24.3, "avg_ttft_ms": 180},
      "cases": [
        {
          "name": "Capital of France",
          "prompt": "What is the capital of France?",
          "metrics": {"avg_tok_s": 25.1, "avg_ttft_ms": 150},
          "runs": [
            {"passed": true, "metrics": {"tok_s": 25.1, "ttft_ms": 150, "total_tokens": 42}}
          ]
        }
      ]
    },
    "agent": {
      "metrics": {"reliable_pass_rate": 0.27, "any_pass_rate": 0.73, "avg_iterations": 4.2},
      "cases": [
        {
          "name": "Read and answer",
          "prompt": "Read the file info.txt and tell me what the author's name is.",
          "level": 1,
          "metrics": {"pass_rate": 1.0, "avg_iterations": 1.0, "avg_tool_calls": 1.0},
          "runs": [
            {"passed": true, "metrics": {"iterations": 1, "tool_calls": 1}, "details": {"tool_log": [...]}},
            {"passed": true, "metrics": {"iterations": 1, "tool_calls": 1}, "details": {}},
            {"passed": true, "metrics": {"iterations": 1, "tool_calls": 1}, "details": {}}
          ]
        }
      ]
    }
  }
}
```

### Comparison Logic

When `--compare` is passed:
1. Find the most recent previous result file matching the same model name
2. For each metric in each suite, compute delta (absolute and percentage)
3. Display a delta table: `tok/s: 24.3 → 27.1 (+11.5%)`

If no previous run exists for that model, show current results only.

## Output

### Terminal Report

After a run completes, display a Rich table summarizing all suites.

**Single run (`--runs 1`, default):**
```
Benchmark Results — gemma-4-27b-it-Q4_K_M on localhost:8082
Label: Q4_K_M quant

Speed
  avg tok/s:  24.3    avg TTFT: 180ms

Generation
  avg tok/s:  22.1    avg duration: 45.2s

Code
  avg tok/s:  23.5    parse rate: 100%

Context (degradation)
  10% fill:  25.0 tok/s    90% fill: 18.2 tok/s

Multi-turn
  turn 1:  24.0 tok/s    turn 10: 21.3 tok/s

Agent
  pass rate: 80%    avg iterations: 4.2    avg tool calls: 6.5

E2E Project
  pass rate: 66%    avg iterations: 8.3    avg tool calls: 12.1

Results saved to results/2026-04-13-1430-gemma-4-27b-it-Q4_K_M.json
```

**Multi-run (`--runs 3`):**
```
Agent (3 runs per case)
  Case                     Pass Rate   Runs    Avg Iters   Avg Tools
  Read and answer          3/3         ✓✓✓     1.0         1.0
  Create a file            3/3         ✓✓✓     1.3         1.0
  List and count           2/3         ✓✓✗     2.0         2.3
  Search and report        3/3         ✓✓✓     1.7         1.3
  Read, modify, write      2/3         ✓✗✓     3.0         3.7
  Multi-file creation      1/3         ✗✓✗     4.3         5.0
  Debug a broken script    2/3         ✓✓✗     3.7         4.3
  Create with tests        1/3         ✗✗✓     6.0         8.3
  Refactor across files    1/3         ✓✗✗     5.3         7.7
  CLI tool                 0/3         ✗✗✗     9.0        12.0
  Multi-module project     0/3         ✗✗✗    11.7        15.3

  Reliable (all pass): 3/11    Any pass: 8/11
```

### Delta Report (with --compare)

```
Comparison: Q4_K_M (current) vs Q5_K_M (2026-04-12)

  Metric            Current    Previous    Delta
  avg tok/s         24.3       21.0        +15.7%
  avg TTFT          180ms      210ms       -14.3%
  agent pass rate   80%        60%         +20.0pp
  agent avg iters   4.2        6.1         -31.1%
```

## Dependencies

- `rich` — Terminal table rendering (already used by llama-chat)

No other dependencies needed. The tool uses only stdlib for subprocess management, JSON handling, and regex parsing.
