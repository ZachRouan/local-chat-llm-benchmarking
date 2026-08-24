# local-chat-llm-benchmarking

[![tests](https://github.com/ZachRouan/local-chat-llm-benchmarking/actions/workflows/tests.yml/badge.svg)](https://github.com/ZachRouan/local-chat-llm-benchmarking/actions/workflows/tests.yml)

Benchmark harness for [llama-chat](https://github.com/ZachRouan/llama-chat), a terminal chat client and coding agent for llama.cpp. It measures inference performance (tok/s, TTFT, context-scaling) and — the part I actually care about — **whether a local model can do real agentic coding work**: 25 tasks across 10 difficulty levels, each verified functionally by running the model's output.

The harness drives the chat app as a subprocess with no shared code, so it tests the real app exactly as a user experiences it.

## What it answers

- Did swapping quants (Q4_K_M → Q5_K_S → IQ4_XS) change agent pass rate, or just tok/s?
- Does this model reliably fix a race condition, or pass 1 in 3 at temperature 1.0?
- How much does throughput degrade at 90% context fill?
- Did a llama.cpp build or chat-template change regress anything? (`--compare`)

## Example output

Real run: Qwen3.8-27B (IQ4_XS) on a single consumer GPU, all seven suites. The full JSON is in [`examples/`](examples/2026-08-20-Qwen3.8-27B-UD-IQ4_XS.json).

```
Benchmark Results — Qwen3.8-27B-UD-IQ4_XS.gguf on localhost:8081
Label: baseline-qwen3.8-UD-IQ4_XS-b10450-tuned

speed
  avg_tok_s: 45.0    avg_ttft_ms: 676.1

generation
  avg_tok_s: 34.8    avg_duration_s: 121.1

code
  avg_tok_s: 55.6    parse_rate: 1.0

context
  10% fill_tok_s: 42.5    25% fill_tok_s: 40.8    50% fill_tok_s: 38.1    75% fill_tok_s: 35.8    90% fill_tok_s: 31.8

multiturn
  Turn 1_tok_s: 34.5    Turn 2_tok_s: 31.8    ...    Turn 8_tok_s: 29.8

agent (3 runs per case)
  Case                         Pass Rate    Runs    Avg Iters    Avg Tools
  Read and answer                    3/3    ✓✓✓           2.0          1.0
  Create a file                      3/3    ✓✓✓           3.0          2.0
  List and count                     3/3    ✓✓✓           3.0          2.0
  Search and report                  2/3    ✓✗✓           3.0          3.0
  Read, modify, write                3/3    ✓✓✓           3.0          2.0
  Multi-file creation                3/3    ✓✓✓           4.0          4.0
  Debug a broken script              3/3    ✓✓✓           6.3          6.0
  Create project with tests          3/3    ✓✓✓           5.3          5.3
  Refactor across files              3/3    ✓✓✓           7.0          9.3
  Reliable (all pass): 8/9    Any pass: 9/9

e2e_project
  Case                                 Pass Rate    Runs    Iters    Tools
  CLI tool                                   1/1    ✓        12.0     11.0
  Multi-module project                       0/1    ✗        13.0     14.0
  REST API with persistence                  0/1    ✗        15.0     15.0
  Multi-step data pipeline                   1/1    ✓        15.0     16.0
  Configuration system                       1/1    ✓         9.0     10.0
  Fix a multi-file bug                       1/1    ✓        11.0     12.0
  Untangle spaghetti code                    1/1    ✓        12.0     13.0
  Race condition fix                         1/1    ✓         5.0      5.0
  Markdown to HTML converter                 1/1    ✓         6.0      6.0
  Log parser with pattern matching           1/1    ✓        13.0     14.0
  Key-value store with TCP protocol          1/1    ✓        15.0     16.0
  Job queue with workers                     1/1    ✓        14.0     13.0
  File sync tool                             0/1    ✗        15.0     17.0
  Plugin system                              0/1    ✗        10.0     14.0
  Chat room server                           0/1    ✗        15.0     16.0
  Database-backed CRUD app                   0/1    ✗        15.0     16.0
  Reliable (all pass): 9/16    Any pass: 9/16
```

A 27B model at 4-bit passes every level-1–4 task and most level 5–8 tasks, then falls over on level 9–10 multi-component systems — most of those failures hit the tool-iteration cap mid-build. That is exactly the kind of thing this tool exists to make visible.

## Setup

Prerequisites: Python 3.10+, [llama-chat](https://github.com/ZachRouan/llama-chat) installed and on `PATH` as `llama-chat`, and a llama.cpp server running with a model loaded.

```bash
git clone https://github.com/ZachRouan/local-chat-llm-benchmarking.git
cd local-chat-llm-benchmarking
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python benchmark.py --server localhost:8081                          # all suites
python benchmark.py --server localhost:8081 --suite speed,agent      # some suites
python benchmark.py --server localhost:8081 --suite e2e_project --level 7,8
python benchmark.py --server localhost:8081 --suite agent --runs 5   # more samples per case
python benchmark.py --server localhost:8081 --compare                # delta vs last run of same model
python benchmark.py --server localhost:8081 --label "Q4_K_M, fa on"  # tag the run
python benchmark.py --results results/2026-08-20-1929-Qwen3.8-27B-UD-IQ4_XS.gguf.json
python benchmark.py --list
```

| Argument | Description |
|---|---|
| `--server` | Required. `host:port` of the llama.cpp server |
| `--suite` | Comma-separated suite names (default: all) |
| `--level` | Only run agent/e2e cases at these difficulty levels, e.g. `6` or `6,7` |
| `--runs N` | Runs per case. Default: 3 for `agent`, 1 for everything else |
| `--compare` | Show deltas against the most recent previous run for the same model |
| `--label` | Tag the run (quant, server flags, template version, …) |
| `--temperature` | Sampling temperature (default 1.0, recorded in results) |
| `--max-tokens` | Override max tokens per response |
| `--results FILE` | Render a saved result file |
| `--list` | List available suites |

While a run is in progress, `results/progress.json` is rewritten after every case (current suite/case, per-case pass/fail and metrics so far) so a long run can be watched from another terminal or a dashboard.

## Suites

### Performance

| Suite | Cases | What it measures |
|---|---|---|
| `speed` | 7 short Q&A prompts | Baseline tok/s and TTFT |
| `generation` | 3 long-form prompts | Sustained throughput over long outputs |
| `code` | 5 code-generation prompts | tok/s plus syntax validity (`ast.parse`) |
| `context` | 5 fill levels (10–90%) | tok/s degradation as the context window fills |
| `multiturn` | 8-turn conversation | Per-turn tok/s as context accumulates |

Context is cleared between prompts so each measurement starts clean.

### Agentic

| Suite | Cases | Levels | Default runs |
|---|---|---|---|
| `agent` | 9 | 1–4 | 3 |
| `e2e_project` | 16 | 5–10 | 1 |

Every case has a **setup** function (builds the starting directory), a **task** string (the only thing the model sees), and a **verify** function that exercises the result — runs the produced CLI, starts the produced server and hits its endpoints, opens TCP connections, runs the model's own tests under pytest, checks that files it shouldn't have touched are intact. No LLM-as-judge anywhere; a case passes only if the code works.

Each run gets its own fresh directory under `test-programs/` and a fresh app process started from that directory, so tool calls are naturally sandboxed to the case. Directories are kept after the run so you can inspect what the model built.

| Level | Theme | Cases |
|---|---|---|
| 1 | Single tool call | Read and answer · Create a file |
| 2 | 2–3 tool calls | List and count · Search and report (TODO inside a string literal is the trap) |
| 3 | Multiple tools + reasoning | Read/modify/write JSON · Multi-file package · Debug a NameError |
| 4 | Planning + self-verification | Module with pytest tests · Refactor duplicate across files |
| 5 | Full small project | argparse CLI with JSON persistence · Three-module URL shortener |
| 6 | Multi-component | REST API with persistence · CSV→JSON→report pipeline · Config system with env overrides |
| 7 | Debugging & reasoning | Multi-file cart/discount bug · Untangle a spaghetti function · Race condition |
| 8 | Protocols & formats | Markdown→HTML converter · Log analyzer · TCP key-value store |
| 9 | System integration | File-based job queue with worker · One-way file sync with `--dry-run` · Plugin system |
| 10 | Full application | Threaded multi-client chat room · SQLite contact manager with CSV/JSON export |

Level 7 setups plant a specific bug — e.g. a counter whose `increment()` does an unlocked read → sleep → write — and the verifier checks both that the bug is gone (the threaded test is run five times) and that pre-existing tests still pass. Levels 8–10 verifiers use `verify_helpers.py` to start the model's server on a free port, talk to it, and tear it down.

## Metrics

Per-prompt metrics come from machine-readable `@@BENCH@@` JSON records the chat app emits when launched with `LLAMA_BENCH_JSON=1` — never from scraping rendered terminal output, which is wrapped, buffered, and lossy. When the llama.cpp server returns `timings`, those are used for token counts and decode rate (`timings_source: "server"`); otherwise the app's client-side stream timings are used. A turn with no bench records is an error, not a zero.

| Metric | Description |
|---|---|
| `ttft_ms` | Prompt sent → first streamed token (includes reasoning) |
| `first_content_ms` | Prompt sent → first non-reasoning content token |
| `tok_s` | Decode rate over completion tokens |
| `prefill_tok_s` | Prompt-processing rate |
| `total_tokens` / `duration_s` / `prompt_ms` | Completion size and wall time |
| `context_used` | Prompt + completion tokens at end of turn |
| `hit_max_tokens` | Whether any iteration was cut off by the token limit |
| `reasoning_chars` | Size of the hidden reasoning stream |

Agentic runs add `iterations` (tool-loop turns), `tool_calls`, `tool_errors`, `self_verified` (the model ran a command to check its own work), and `passed`.

Results are saved to `results/YYYY-MM-DD-HHMM-<model>.json` with the server, context length, temperature, label, and llama.cpp build fingerprint, so any two runs can be compared knowing what changed.

## How it works

`benchmark.py` resolves `llama-chat` on `PATH` to find the app's interpreter and `main.py`, then launches `python -u main.py` with `LLAMA_SERVERS` pointing at the target server, `LLAMA_BENCH_JSON=1`, a pinned temperature, and a raised tool-iteration cap. It reads stdout byte-by-byte (the app's `input()` prompts have no trailing newline), auto-answers the model menu and session-resume prompts, waits for the `You >` prompt, and from then on writes prompts and collects `@@BENCH@@` records until the prompt returns. A 600 s silence is treated as a dead turn: agentic suites record it as a failed run and continue with the next one; a performance suite that dies is recorded as a suite error, the app is restarted, and the remaining suites still run — completed results are never discarded.

```
benchmark.py              CLI, progress file, run orchestration
benchmarks/runner.py      AppClient — subprocess lifecycle, bench-record parsing
benchmarks/results.py     JSON save/load, previous-run lookup, delta computation
benchmarks/report.py      Rich tables
benchmarks/suites/        one module per suite; agent.py + e2e_project.py hold the 25 cases
benchmarks/suites/verify_helpers.py   free ports, server start/stop, HTTP + TCP probes
docs/                     original design documents
examples/                 a complete real result file
```

## Tests

```bash
python -m pytest tests/ -q
```

95 tests covering bench-record parsing, result storage and comparison, report rendering, suite registration, CLI behavior, and the case setup/verify functions (setups produce the intended fixtures; verifiers reject missing or wrong output). No model or server needed.

## License

MIT
