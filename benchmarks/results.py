"""Save, load, and compare benchmark result JSON files."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def save_results(data: dict, results_dir: Path) -> Path:
    """Save results to a timestamped JSON file. Returns the file path."""
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    model = data.get("model", "unknown")
    safe_model = re.sub(r"[^\w\-.]", "-", model)
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        dt = datetime.now(timezone.utc)
    date_str = dt.strftime("%Y-%m-%d-%H%M")
    filename = f"{date_str}-{safe_model}.json"
    path = results_dir / filename
    path.write_text(json.dumps(data, indent=2) + "\n")
    return path


def load_results(path: Path) -> dict:
    """Load results from a JSON file."""
    return json.loads(path.read_text())


def find_previous_result(
    model: str,
    results_dir: Path,
    exclude: Path | None = None,
) -> Path | None:
    """Find the most recent result file for the given model, excluding a specific file."""
    if not results_dir.exists():
        return None
    safe_model = re.sub(r"[^\w\-.]", "-", model)
    candidates = sorted(
        [
            p
            for p in results_dir.glob(f"*-{safe_model}.json")
            if p != exclude
        ],
        reverse=True,
    )
    return candidates[0] if candidates else None


def compute_deltas(current: dict, previous: dict) -> dict:
    """Compute metric deltas between current and previous results.

    Returns a dict keyed by suite name, then metric name, with:
        {"current": float, "previous": float | None, "delta": float | None, "delta_pct": float | None}
    """
    deltas: dict = {}
    for suite_name, suite_data in current.get("suites", {}).items():
        suite_deltas: dict = {}
        current_metrics = suite_data.get("metrics", {})
        prev_suite = previous.get("suites", {}).get(suite_name, {})
        prev_metrics = prev_suite.get("metrics", {})

        for metric_name, current_val in current_metrics.items():
            prev_val = prev_metrics.get(metric_name)
            delta = None
            delta_pct = None
            if prev_val is not None and current_val is not None:
                delta = current_val - prev_val
                if prev_val != 0:
                    delta_pct = (delta / prev_val) * 100
            suite_deltas[metric_name] = {
                "current": current_val,
                "previous": prev_val,
                "delta": delta,
                "delta_pct": delta_pct,
            }
        deltas[suite_name] = suite_deltas
    return deltas
