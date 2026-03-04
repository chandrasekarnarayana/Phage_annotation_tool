from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
JUNIT_SCRIPT = ROOT / "scripts" / "check_junit_executed.py"
BENCH_SCRIPT = ROOT / "scripts" / "check_benchmark_thresholds.py"
BENCH_TREND_SCRIPT = ROOT / "scripts" / "compare_benchmark_baseline.py"
CI_SUMMARY_SCRIPT = ROOT / "scripts" / "build_ci_summary.py"


def test_junit_gate_passes_with_executed_tests(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite name="x" tests="5" skipped="1"></testsuite>\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(JUNIT_SCRIPT), str(report), "--min-executed", "3"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_junit_gate_fails_when_all_skipped(tmp_path: Path) -> None:
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite name="x" tests="4" skipped="4"></testsuite>\n',
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(JUNIT_SCRIPT), str(report)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1


def test_benchmark_threshold_gate_passes(tmp_path: Path) -> None:
    bench = tmp_path / "bench.json"
    thresholds = tmp_path / "thresholds.json"
    bench.write_text(
        json.dumps(
            {
                "benchmarks": [
                    {"fullname": "tests/performance/test_perf.py::test_standardize_axes_perf", "stats": {"mean": 0.01}}
                ]
            }
        ),
        encoding="utf-8",
    )
    thresholds.write_text(
        json.dumps({"checks": [{"match": "standardize_axes_perf", "max_mean_ms": 50.0}]}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT), str(bench), str(thresholds)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0


def test_benchmark_threshold_gate_fails_on_regression(tmp_path: Path) -> None:
    bench = tmp_path / "bench.json"
    thresholds = tmp_path / "thresholds.json"
    bench.write_text(
        json.dumps(
            {
                "benchmarks": [
                    {"fullname": "tests/performance/test_perf.py::test_standardize_axes_perf", "stats": {"mean": 1.0}}
                ]
            }
        ),
        encoding="utf-8",
    )
    thresholds.write_text(
        json.dumps({"checks": [{"match": "standardize_axes_perf", "max_mean_ms": 100.0}]}),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(BENCH_SCRIPT), str(bench), str(thresholds)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1


def test_benchmark_trend_report_script_writes_markdown(tmp_path: Path) -> None:
    bench = tmp_path / "bench.json"
    baseline = tmp_path / "baseline.json"
    out = tmp_path / "trend.md"
    bench.write_text(
        json.dumps(
            {
                "benchmarks": [
                    {"fullname": "tests/performance/test_perf.py::test_standardize_axes_perf", "stats": {"mean": 0.02}}
                ]
            }
        ),
        encoding="utf-8",
    )
    baseline.write_text(
        json.dumps(
            {
                "baselines": [
                    {"match": "standardize_axes_perf", "mean_ms": 10.0, "max_regression_pct": 300.0}
                ]
            }
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [sys.executable, str(BENCH_TREND_SCRIPT), str(bench), str(baseline), "--output", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert out.exists()
    assert "Benchmark Trend Report" in out.read_text(encoding="utf-8")


def test_ci_summary_script_builds_expected_sections(tmp_path: Path) -> None:
    artifacts = tmp_path / "artifacts_download"
    (artifacts / "gui").mkdir(parents=True, exist_ok=True)
    (artifacts / "perf").mkdir(parents=True, exist_ok=True)
    (artifacts / "gui" / "junit-gui.xml").write_text(
        '<testsuite name="gui" tests="10" skipped="2"></testsuite>\n', encoding="utf-8"
    )
    (artifacts / "gui" / "junit-gui-ux-state.xml").write_text(
        '<testsuite name="guiux" tests="4" skipped="1"></testsuite>\n', encoding="utf-8"
    )
    (artifacts / "perf" / "junit-performance-gate.xml").write_text(
        '<testsuite name="perf" tests="3" skipped="0"></testsuite>\n', encoding="utf-8"
    )
    (artifacts / "perf" / "benchmark-gate.json").write_text(
        json.dumps({"benchmarks": [{"fullname": "test_standardize_axes_perf", "stats": {"mean": 0.01}}]}),
        encoding="utf-8",
    )
    thresholds = tmp_path / "thresholds.json"
    thresholds.write_text(
        json.dumps({"checks": [{"match": "standardize_axes_perf", "max_mean_ms": 100.0}]}),
        encoding="utf-8",
    )
    out = tmp_path / "ci-summary.md"
    proc = subprocess.run(
        [
            sys.executable,
            str(CI_SUMMARY_SCRIPT),
            "--artifacts-dir",
            str(artifacts),
            "--thresholds",
            str(thresholds),
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "CI Quality Summary" in text
    assert "GUI Execution" in text
    assert "Benchmark Thresholds" in text
