"""Validate pytest-benchmark JSON output against configured thresholds."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    """Load json for the current workflow."""
    return json.loads(path.read_text(encoding="utf-8"))


def _benchmark_label(entry: dict[str, Any]) -> str:
    """Handle the benchmark label helper flow."""
    for key in ("fullname", "fullfunc", "name"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "<unknown>"


def main() -> int:
    """Run the main workflow."""
    parser = argparse.ArgumentParser(description="Check benchmark JSON against thresholds.")
    parser.add_argument("benchmark_json", type=Path, help="Path to --benchmark-json output file.")
    parser.add_argument("thresholds_json", type=Path, help="Threshold definition JSON.")
    args = parser.parse_args()

    if not args.benchmark_json.exists():
        print(f"Benchmark JSON missing: {args.benchmark_json}", file=sys.stderr)
        return 2
    if not args.thresholds_json.exists():
        print(f"Threshold config missing: {args.thresholds_json}", file=sys.stderr)
        return 2

    bench_payload = _load_json(args.benchmark_json)
    threshold_payload = _load_json(args.thresholds_json)
    entries = list(bench_payload.get("benchmarks", []))
    checks = list(threshold_payload.get("checks", []))

    failures: list[str] = []
    matched = 0

    for rule in checks:
        pattern = str(rule.get("match", "")).strip()
        max_mean_ms = float(rule.get("max_mean_ms", 0.0))
        if not pattern or max_mean_ms <= 0:
            failures.append(f"Invalid threshold rule: {rule}")
            continue
        regex = re.compile(pattern)
        found = False
        for entry in entries:
            label = _benchmark_label(entry)
            if not regex.search(label):
                continue
            found = True
            stats = entry.get("stats", {})
            mean_sec = float(stats.get("mean", 0.0))
            mean_ms = mean_sec * 1000.0
            matched += 1
            print(f"[BENCH] {label}: mean={mean_ms:.3f} ms (limit={max_mean_ms:.3f} ms)")
            if mean_ms > max_mean_ms:
                failures.append(
                    f"{label}: mean {mean_ms:.3f} ms exceeds threshold {max_mean_ms:.3f} ms"
                )
        if not found:
            failures.append(f"No benchmark matched pattern: {pattern}")

    if matched == 0:
        failures.append("No benchmark entries matched any threshold rule.")

    if failures:
        print("Benchmark threshold check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("Benchmark threshold checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
