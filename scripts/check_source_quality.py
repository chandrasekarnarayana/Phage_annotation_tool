#!/usr/bin/env python3
"""Validate source docstrings and modularity size targets."""

from __future__ import annotations

import ast
from pathlib import Path
import sys


ROOT = Path.cwd()
SOURCE_ROOTS = (
    ROOT / "src",
    ROOT / "tests",
    ROOT / "scripts",
)
EXCLUDED_PARTS = {
    "__pycache__",
}
SOFT_LINE_LIMIT = 300
FUNCTION_WARNING_SAMPLE_LIMIT = 60


def _iter_python_files() -> list[Path]:
    """Handle the iter python files helper flow."""
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        if not source_root.exists():
            continue
        for path in source_root.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def _relative(path: Path) -> str:
    """Handle the relative helper flow."""
    return path.relative_to(ROOT).as_posix()


def _parse_module(path: Path) -> ast.Module | None:
    """Parse a Python file and return None when syntax is invalid."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return None


def _iter_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return all function nodes, including methods and nested helpers."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def main() -> int:
    """Run source quality checks and print actionable findings."""
    missing_docstrings: list[str] = []
    missing_function_docstrings: list[str] = []
    oversized_files: list[str] = []

    for path in _iter_python_files():
        rel_path = _relative(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        tree = _parse_module(path)
        if tree is None or ast.get_docstring(tree) is None:
            missing_docstrings.append(rel_path)
        if tree is not None:
            for node in _iter_functions(tree):
                if ast.get_docstring(node) is None:
                    missing_function_docstrings.append(f"{rel_path}:{node.lineno}:{node.name}")
        if len(lines) > SOFT_LINE_LIMIT:
            oversized_files.append(f"{rel_path} ({len(lines)} lines)")

    if missing_docstrings:
        sys.stderr.write("Source quality checks failed.\n")
        sys.stderr.write("\nPython files missing module docstrings:\n")
        for item in missing_docstrings:
            sys.stderr.write(f"  - {item}\n")
        return 1

    if oversized_files:
        sys.stderr.write(
            f"Source modularity warning: files over {SOFT_LINE_LIMIT} lines remain.\n"
        )
        for item in oversized_files:
            sys.stderr.write(f"  - {item}\n")

    if missing_function_docstrings:
        sys.stderr.write(
            "Source documentation warning: functions without docstrings/comments remain "
            f"({len(missing_function_docstrings)} total).\n"
        )
        for item in missing_function_docstrings[:FUNCTION_WARNING_SAMPLE_LIMIT]:
            sys.stderr.write(f"  - {item}\n")
        remaining = len(missing_function_docstrings) - FUNCTION_WARNING_SAMPLE_LIMIT
        if remaining > 0:
            sys.stderr.write(f"  ... {remaining} more\n")

    print("Source quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
