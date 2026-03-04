"""Compare current pytest-benchmark JSON against a lightweight baseline spec.

This script is intentionally non-blocking by default. It writes a markdown
report and returns zero unless --fail-on-regression is provided.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _label(entry: dict[str, Any]) -> str:
    for key in ("fullname", "fullfunc", "name"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "<unknown>"


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare benchmark run vs baseline.")
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument("baseline_json", type=Path)
    parser.add_argument("--output", type=Path, default=Path("artifacts/benchmark-trend.md"))
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    lines = ["# Benchmark Trend Report", ""]
    failures: list[str] = []

    if not args.benchmark_json.exists():
        msg = f"Benchmark output not found: {args.benchmark_json}"
        lines.append(f"- {msg}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(msg, file=sys.stderr)
        return 2

    bench = _load_json(args.benchmark_json)
    entries = list(bench.get("benchmarks", []))
    if not args.baseline_json.exists():
        lines.append(f"- Baseline file not found: `{args.baseline_json}`")
        lines.append("- Skipping trend comparison.")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("No baseline file; trend comparison skipped.")
        return 0

    baseline = _load_json(args.baseline_json)
    rules = list(baseline.get("baselines", []))
    lines.append(f"- Benchmarks in run: {len(entries)}")
    lines.append(f"- Baseline rules: {len(rules)}")
    lines.append("")
    lines.append("| Pattern | Baseline (ms) | Current (ms) | Delta % | Status |")
    lines.append("|---|---:|---:|---:|---|")

    for rule in rules:
        pattern = str(rule.get("match", "")).strip()
        base_ms = float(rule.get("mean_ms", 0.0))
        max_reg = float(rule.get("max_regression_pct", 30.0))
        if not pattern or base_ms <= 0:
            continue
        regex = re.compile(pattern)
        matched = None
        for entry in entries:
            if regex.search(_label(entry)):
                matched = entry
                break
        if matched is None:
            lines.append(f"| `{pattern}` | {base_ms:.3f} | n/a | n/a | missing |")
            continue
        cur_ms = float(matched.get("stats", {}).get("mean", 0.0)) * 1000.0
        delta_pct = ((cur_ms - base_ms) / base_ms) * 100.0
        status = "ok"
        if delta_pct > max_reg:
            status = f"regressed (> {max_reg:.1f}%)"
            failures.append(f"{pattern}: +{delta_pct:.2f}%")
        lines.append(f"| `{pattern}` | {base_ms:.3f} | {cur_ms:.3f} | {delta_pct:.2f} | {status} |")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote benchmark trend report: {args.output}")

    if args.fail_on_regression and failures:
        print("Benchmark regression failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
