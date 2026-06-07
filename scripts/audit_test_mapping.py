#!/usr/bin/env python3
"""Audit how test files map to source modules.

The script scans `src/phage_annotator` for importable modules and reports
which modules are referenced by `tests/test_*.py` imports.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "phage_annotator"
TEST_ROOT = REPO_ROOT / "tests"


def iter_source_modules() -> list[str]:
    """Return dotted module names for source files under `src/phage_annotator`."""
    modules: list[str] = []
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(SRC_ROOT)
        if rel.name == "__init__.py":
            continue
        dotted = "phage_annotator." + ".".join(rel.with_suffix("").parts)
        modules.append(dotted)
    return modules


def _iter_imported_modules(tree: ast.AST) -> Iterable[str]:
    """Handle the iter imported modules helper flow."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("phage_annotator"):
                    yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("phage_annotator"):
                yield node.module


def map_modules_to_tests() -> dict[str, set[str]]:
    """Return source-module -> test-file mapping based on imports."""
    source_modules = iter_source_modules()
    mapping: dict[str, set[str]] = {name: set() for name in source_modules}
    for test_file in sorted(TEST_ROOT.rglob("test_*.py")):
        tree = ast.parse(test_file.read_text(encoding="utf-8"))
        imported = set(_iter_imported_modules(tree))
        for module_name in source_modules:
            if module_name in imported:
                mapping[module_name].add(str(test_file.relative_to(TEST_ROOT)))
    return mapping


def main() -> int:
    """Print audit summary."""
    mapping = map_modules_to_tests()
    total = len(mapping)
    covered = sum(1 for tests in mapping.values() if tests)
    uncovered = total - covered

    print(f"Source modules scanned: {total}")
    print(f"Modules referenced by tests: {covered}")
    print(f"Modules without direct test imports: {uncovered}")

    if uncovered:
        print("\nTop uncovered modules:")
        count = 0
        for module_name, tests in sorted(mapping.items()):
            if tests:
                continue
            print(f"  - {module_name}")
            count += 1
            if count >= 25:
                break
        if uncovered > 25:
            print(f"  ... and {uncovered - 25} more")

    package_totals: dict[str, int] = {}
    package_covered: dict[str, int] = {}
    for module_name, tests in mapping.items():
        parts = module_name.split(".")
        pkg = parts[1] if len(parts) > 2 else "(root)"
        package_totals[pkg] = package_totals.get(pkg, 0) + 1
        if tests:
            package_covered[pkg] = package_covered.get(pkg, 0) + 1

    print("\nPackage-level coverage:")
    for pkg in sorted(package_totals):
        pkg_total = package_totals[pkg]
        pkg_cov = package_covered.get(pkg, 0)
        pct = 100.0 * pkg_cov / pkg_total if pkg_total else 0.0
        print(f"  - {pkg}: {pkg_cov}/{pkg_total} ({pct:.1f}%)")

    print("\nTop covered modules:")
    shown = 0
    for module_name, tests in sorted(
        mapping.items(), key=lambda kv: (-len(kv[1]), kv[0])
    ):
        if not tests:
            continue
        print(f"  - {module_name}: {len(tests)} test file(s)")
        shown += 1
        if shown >= 15:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
