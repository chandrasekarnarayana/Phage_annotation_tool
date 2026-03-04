"""Fail CI when a pytest JUnit report contains zero executed tests.

Executed tests are computed as:
    executed = tests - skipped
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _parse_counts(xml_path: Path) -> tuple[int, int]:
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    if root.tag == "testsuite":
        tests = int(root.attrib.get("tests", "0"))
        skipped = int(root.attrib.get("skipped", "0"))
        return tests, skipped
    tests = 0
    skipped = 0
    for suite in root.findall(".//testsuite"):
        tests += int(suite.attrib.get("tests", "0"))
        skipped += int(suite.attrib.get("skipped", "0"))
    return tests, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure JUnit report has executed tests.")
    parser.add_argument("junit_xml", type=Path, help="Path to pytest JUnit XML report.")
    parser.add_argument(
        "--min-executed",
        type=int,
        default=1,
        help="Minimum number of executed tests required.",
    )
    args = parser.parse_args()

    if not args.junit_xml.exists():
        print(f"JUnit report not found: {args.junit_xml}", file=sys.stderr)
        return 2

    tests, skipped = _parse_counts(args.junit_xml)
    executed = max(0, tests - skipped)
    print(f"JUnit summary: tests={tests} skipped={skipped} executed={executed}")

    if executed < args.min_executed:
        print(
            f"Executed test count {executed} is below required minimum {args.min_executed}.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
