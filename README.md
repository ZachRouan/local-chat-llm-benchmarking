# llama-chat-benchmarking

Benchmark suite for [llama-chat](https://github.com/ZachRouan/local-chat-llm) — measures inference performance, coding agent efficiency, and detects regressions across models and configurations.

Drives the chat app as a subprocess (no imports, fully decoupled) so it tests the real app exactly as a user experiences it.

## Prerequisites

- [llama-chat](https://github.com/ZachRouan/local-chat-llm) installed and available as `llama-chat` in PATH
- A llama.cpp server running with a model loaded
- Python 3.10+

## Setup

```bash
git clone https://github.com/ZachRouan/local-chat-llm-benchmarking.git
cd local-chat-llm-benchmarking
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
# Run all suites
python benchmark.py --server localhost:8081

# Run specific suites
python benchmark.py --server localhost:8081 --suite speed,agent

# Run with multiple attempts per test case
python benchmark.py --server localhost:8081 --suite agent --runs 3

# Compare against previous run for the same model
python benchmark.py --server localhost:8081 --compare

# Tag a run (e.g., quant type, GPU config)
python benchmark.py --server localhost:8081 --label "Q4_K_M quant"

# List available suites
python benchmark.py --list

# View results from a previous run
python benchmark.py --results results/2026-04-13-1652-gemma-4-26B.json
```

### Arguments

| Argument | Description |
|---|---|
| `--server` | Required. `host:port` of the llama.cpp server |
| `--suite` | Comma-separated suite names (default: all) |
| `--runs N` | Repeat each test case N times (default: 1) |
| `--compare` | Show delta against most recent previous run for the same model |
| `--label` | Tag the run with a label |
| `--list` | List available suites and exit |
| `--results` | Display results from a JSON file |
| `--temperature` | Override sampling temperature |
| `--max-tokens` | Override max tokens per response |

## Benchmark Suites

### Performance Suites

| Suite | Cases | What it measures |
|---|---|---|
| **speed** | 7 short Q&A prompts | Baseline tok/s and TTFT |
| **generation** | 3 long-form prompts | Sustained throughput over longer outputs |
| **code** | 5 code generation prompts | tok/s + syntax validity (`ast.parse`) |
| **context** | 5 fill levels (10%-90%) | How tok/s degrades as context window fills |
| **multiturn** | 8-turn conversation | Per-turn performance as context accumulates |

All performance suites clear context between prompts for clean measurements.

### Agent Suites

| Suite | Cases | Levels | What it measures |
|---|---|---|---|
| **agent** | 9 cases | 1-4 | Tool use accuracy, iteration count, self-verification |
| **e2e_project** | 2 cases | 5 | Full project creation with tests |

Agent suites restart the app per case in its own working directory under `test-programs/`. Files are kept after runs so you can inspect what the model produced.

### Agent Test Cases

| # | Name | Level | Task |
|---|---|---|---|
| 1 | Read and answer | 1 | Read a file and extract information |
| 2 | Create a file | 1 | Create a file with exact content |
| 3 | List and count | 2 | Count Python files in a directory |
| 4 | Search and report | 2 | Find TODO comments (with edge case: TODO in string literal) |
| 5 | Read, modify, write | 3 | Change a value in a JSON config without corrupting other fields |
| 6 | Multi-file creation | 3 | Create a Python package with working imports |
| 7 | Debug a broken script | 3 | Find and fix a NameError bug |
| 8 | Create project with tests | 4 | Write a module + pytest tests, run them |
| 9 | Refactor across files | 4 | Extract duplicated function into shared module |
| 10 | CLI tool | 5 | Build a task manager CLI with argparse, JSON persistence, tests |
| 11 | Multi-module project | 5 | Build a URL shortener with 3 modules, CLI, and tests |

Each case has a **setup** function (creates the starting environment), a **task** string (sent to the model), and a **verify** function (runs the output, checks exit codes, asserts file contents).

## Metrics

### Core (all suites)

| Metric | Description |
|---|---|
| `ttft_ms` | Time to first token (includes reasoning time) |
| `tok_s` | Tokens per second |
| `total_tokens` | Completion token count |
| `duration_s` | Wall clock generation time |
| `context_used` | Prompt + completion tokens |

### Agent-specific

| Metric | Description |
|---|---|
| `iterations` | Number of tool loop iterations |
| `tool_calls` | Total tool calls made |
| `tool_errors` | Tool calls that returned errors |
| `self_verified` | Whether the model ran verification commands |
| `passed` | Whether the output passed the verify function |

## Multi-Run Mode (`--runs N`)

When `--runs N` is greater than 1, each test case runs N times independently. Agent cases get separate directories (`cli-tool/`, `cli-tool-run2/`, `cli-tool-run3/`).

```
Agent (3 runs per case)
  Case                     Pass Rate   Runs    Avg Iters   Avg Tools
  Read and answer          3/3         ✓✓✓     1.0         1.0
  Create a file            3/3         ✓✓✓     1.3         1.0
  List and count           2/3         ✓✓✗     2.0         2.3
  ...
  CLI tool                 0/3         ✗✗✗     9.0        12.0

  Reliable (all pass): 3/11    Any pass: 8/11
```

Summary metrics:
- **reliable_pass_rate** — Fraction of cases that passed all N runs
- **any_pass_rate** — Fraction of cases that passed at least one run

## Results

Results are saved as JSON to `results/YYYY-MM-DD-HHMM-<model-name>.json`. Use `--compare` to show deltas against the previous run:

```
Comparison: Q4_K_M (current) vs Q5_K_M (2026-04-12)

  Metric            Current    Previous    Delta
  avg tok/s         24.3       21.0        +15.7%
  avg TTFT          180ms      210ms       -14.3%
  agent pass rate   80%        60%         +20.0pp
```

## Output Directories

| Path | Purpose |
|---|---|
| `results/` | JSON result files (gitignored) |
| `test-programs/` | Agent/E2E working directories (gitignored, inspectable) |

## How It Works

The benchmark tool resolves `llama-chat` from PATH, finds its Python interpreter and `main.py`, and launches it as a subprocess with `LLAMA_SERVERS` set to the target server.

It reads stdout byte-by-byte (since `input()` prompts don't end with newlines), navigates the model selection menu automatically, and parses the stats line the app already prints after every response:

```
1653 tokens in 73.0s (22.7 tok/s) · context: 1,676/100,096 (2%)
```

For agent suites, it also parses tool call output (`→ read_file: main.py`, `✓ (42 lines)`, `✗ Error: ...`).

## Tests

```bash
python -m pytest tests/ -v
```

62 tests covering parsers, data types, results storage, report rendering, suite registration, agent case setup/verify functions, and CLI behavior.
