"""Build a markdown summary from CI artifacts (GUI + performance gates)."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _find_one(root: Path, name: str) -> Path | None:
    """Find one for the current workflow."""
    for path in root.rglob(name):
        return path
    return None


def _parse_junit(path: Path) -> tuple[int, int, int]:
    """Parse junit for the current workflow."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    if root.tag == "testsuite":
        tests = int(root.attrib.get("tests", "0"))
        skipped = int(root.attrib.get("skipped", "0"))
        return tests, skipped, max(0, tests - skipped)
    tests = skipped = 0
    for suite in root.findall(".//testsuite"):
        tests += int(suite.attrib.get("tests", "0"))
        skipped += int(suite.attrib.get("skipped", "0"))
    return tests, skipped, max(0, tests - skipped)


def _bench_label(entry: dict[str, Any]) -> str:
    """Handle the bench label helper flow."""
    for key in ("fullname", "fullfunc", "name"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "<unknown>"


def _benchmark_table(bench_path: Path, threshold_path: Path) -> list[str]:
    """Handle the benchmark table helper flow."""
    bench_payload = json.loads(bench_path.read_text(encoding="utf-8"))
    rules_payload = json.loads(threshold_path.read_text(encoding="utf-8"))
    entries = list(bench_payload.get("benchmarks", []))
    rules = list(rules_payload.get("checks", []))

    lines = [
        "",
        "## Benchmark Thresholds",
        "",
        "| Pattern | Mean (ms) | Limit (ms) | Status |",
        "|---|---:|---:|---|",
    ]
    for rule in rules:
        pattern = str(rule.get("match", "")).strip()
        limit = float(rule.get("max_mean_ms", 0.0))
        if not pattern or limit <= 0:
            continue
        regex = re.compile(pattern)
        match = next((entry for entry in entries if regex.search(_bench_label(entry))), None)
        if match is None:
            lines.append(f"| `{pattern}` | n/a | {limit:.3f} | missing |")
            continue
        mean_ms = float(match.get("stats", {}).get("mean", 0.0)) * 1000.0
        status = "pass" if mean_ms <= limit else "fail"
        lines.append(f"| `{pattern}` | {mean_ms:.3f} | {limit:.3f} | {status} |")
    return lines


def main() -> int:
    """Run the main workflow."""
    parser = argparse.ArgumentParser(description="Build CI summary markdown from artifacts.")
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--thresholds", type=Path, default=Path("tests/performance/benchmark_thresholds.json"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/ci-summary.md"))
    args = parser.parse_args()

    lines = ["# CI Quality Summary", ""]
    gui_path = _find_one(args.artifacts_dir, "junit-gui.xml")
    ux_path = _find_one(args.artifacts_dir, "junit-gui-ux-state.xml")
    perf_path = _find_one(args.artifacts_dir, "junit-performance-gate.xml")
    bench_json = _find_one(args.artifacts_dir, "benchmark-gate.json")

    lines.extend(["## GUI Execution", "", "| Suite | Tests | Skipped | Executed |", "|---|---:|---:|---:|"])
    for label, path in (
        ("GUI", gui_path),
        ("GUI UX State", ux_path),
        ("Performance Gate", perf_path),
    ):
        if path is None:
            lines.append(f"| {label} | n/a | n/a | n/a |")
            continue
        tests, skipped, executed = _parse_junit(path)
        lines.append(f"| {label} | {tests} | {skipped} | {executed} |")

    if bench_json is not None and args.thresholds.exists():
        lines.extend(_benchmark_table(bench_json, args.thresholds))
    else:
        lines.extend(["", "## Benchmark Thresholds", "", "- Benchmark artifacts not found in downloaded artifacts."])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote CI summary: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
