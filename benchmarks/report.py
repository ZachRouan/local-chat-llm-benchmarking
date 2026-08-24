"""Rich terminal output for benchmark results and comparisons."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text


# Metrics where a DECREASE is an improvement. Everything else (tok/s,
# pass rates, prefill) improves upward; unknown metrics render neutral.
_LOWER_IS_BETTER = (
    "ttft_ms", "first_content_ms", "duration_s", "prompt_ms",
    "tool_errors", "iterations", "tool_calls", "reasoning_chars",
)
_HIGHER_IS_BETTER = (
    "tok_s", "prefill_tok_s", "pass_rate", "parse_rate", "total_tokens",
)
# Perf metrics vary run-to-run; deltas inside this band are noise, not signal.
_NOISE_FLOOR_PCT = 5.0


def _format_delta(delta_pct: float | None, metric_name: str = "") -> Text:
    """Format a delta percentage, colored by whether it's an improvement."""
    if delta_pct is None:
        return Text("—")
    sign = "+" if delta_pct >= 0 else ""
    text = f"{sign}{delta_pct:.1f}%"

    if abs(delta_pct) < _NOISE_FLOOR_PCT:
        return Text(text, style="dim")

    name = metric_name.lower()
    if any(k in name for k in _LOWER_IS_BETTER):
        improved = delta_pct < 0
    elif any(k in name for k in _HIGHER_IS_BETTER):
        improved = delta_pct > 0
    else:
        return Text(text)
    return Text(text, style="green" if improved else "red")


def _pass_rate_str(runs: list[dict]) -> str:
    """Format pass rate as 'k/N ✓✗✓'."""
    n = len(runs)
    passed = sum(1 for r in runs if r.get("passed", False))
    symbols = "".join("✓" if r.get("passed", False) else "✗" for r in runs)
    return f"{passed}/{n} {symbols}"


def print_summary(data: dict, console: Console | None = None) -> None:
    """Print a summary table of benchmark results."""
    if console is None:
        console = Console()

    model = data.get("model", "unknown")
    server = data.get("server", "unknown")
    label = data.get("label")

    console.print()
    title = f"Benchmark Results — {model} on {server}"
    if label:
        title += f"\nLabel: {label}"
    console.print(f"[bold]{title}[/bold]")
    console.print()

    suites = data.get("suites", {})

    for suite_name, suite_data in suites.items():
        metrics = suite_data.get("metrics", {})
        cases = suite_data.get("cases", [])

        has_pass_rates = any("pass_rate" in c.get("metrics", {}) for c in cases)
        # Run counts are per-suite (each suite has its own default) — infer
        # from the recorded runs rather than a global setting.
        max_runs = max((len(c.get("runs", [])) for c in cases), default=1)

        if has_pass_rates:
            header = suite_name
            if max_runs > 1:
                header += f" ({max_runs} runs per case)"
            console.print(f"[bold]{header}[/bold]")
            table = Table(show_header=True, box=None, padding=(0, 2))
            table.add_column("Case")
            table.add_column("Pass Rate", justify="right")
            table.add_column("Runs")
            table.add_column("Iters" if max_runs == 1 else "Avg Iters", justify="right")
            table.add_column("Tools" if max_runs == 1 else "Avg Tools", justify="right")

            for case in cases:
                cm = case.get("metrics", {})
                runs = case.get("runs", [])
                table.add_row(
                    case.get("name", ""),
                    f"{sum(1 for r in runs if r.get('passed')):d}/{len(runs)}",
                    "".join("✓" if r.get("passed") else "✗" for r in runs),
                    f"{cm.get('avg_iterations', 0):.1f}",
                    f"{cm.get('avg_tool_calls', 0):.1f}",
                )

            console.print(table)

            reliable = metrics.get("reliable_pass_rate")
            any_pass = metrics.get("any_pass_rate")
            if reliable is not None and any_pass is not None:
                total = len(cases)
                console.print(
                    f"  Reliable (all pass): {int(reliable * total)}/{total}"
                    f"    Any pass: {int(any_pass * total)}/{total}"
                )
        else:
            console.print(f"[bold]{suite_name}[/bold]")
            parts = []
            for k, v in metrics.items():
                if v is not None:
                    if isinstance(v, float):
                        parts.append(f"{k}: {v:.1f}")
                    else:
                        parts.append(f"{k}: {v}")
            console.print(f"  {'    '.join(parts)}")

        console.print()


def print_delta_report(
    deltas: dict,
    current_label: str = "current",
    previous_label: str = "previous",
    console: Console | None = None,
) -> None:
    """Print a comparison table showing metric deltas."""
    if console is None:
        console = Console()

    console.print()
    console.print(f"[bold]Comparison: {current_label} vs {previous_label}[/bold]")
    console.print()

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Metric")
    table.add_column("Current", justify="right")
    table.add_column("Previous", justify="right")
    table.add_column("Delta", justify="right")

    for suite_name, suite_deltas in deltas.items():
        for metric_name, d in suite_deltas.items():
            current = d["current"]
            previous = d["previous"]
            current_str = f"{current:.1f}" if isinstance(current, float) else str(current)
            previous_str = (
                f"{previous:.1f}" if isinstance(previous, float) and previous is not None
                else str(previous) if previous is not None
                else "—"
            )
            delta_text = _format_delta(d.get("delta_pct"), metric_name)
            table.add_row(
                f"{suite_name}.{metric_name}",
                current_str,
                previous_str,
                delta_text,
            )

    console.print(table)
    console.print()
