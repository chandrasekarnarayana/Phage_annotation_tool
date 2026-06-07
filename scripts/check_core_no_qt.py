"""Guard against Qt dependencies in core/headless modules.

This script scans `src/phage_annotator` and verifies that non-GUI modules do
not import Qt bindings or the `ui_qt` package.
"""

from __future__ import annotations

import ast
from pathlib import Path
import sys


SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "phage_annotator"

HEADLESS_PACKAGES = {
    "algorithms",
    "annotation",
    "cache",
    "config",
    "constants",
    "core",
    "data",
    "framework",
    "io",
    "tools",
    "utils",
}

HEADLESS_ROOT_MODULES = {
    "__main__.py",
}

FORBIDDEN_IMPORT_PREFIXES = (
    "phage_annotator.ui_qt",
    "matplotlib.backends.qt_compat",
    "matplotlib.backends.backend_qt",
    "PyQt5",
    "PyQt6",
    "PySide2",
    "PySide6",
    "qtpy",
)


def _is_core_candidate(path: Path) -> bool:
    """Return whether core candidate is true for the current state."""
    rel = path.relative_to(SRC_ROOT)
    if "__pycache__" in rel.parts:
        return False
    if rel.parts and rel.parts[0] in HEADLESS_PACKAGES:
        return True
    return len(rel.parts) == 1 and rel.name in HEADLESS_ROOT_MODULES


def _iter_forbidden_imports(path: Path) -> list[str]:
    """Handle the iter forbidden imports helper flow."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    found.append(name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            name = node.module
            if name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                found.append(name)
    return found


def main() -> int:
    """Run the main workflow."""
    violations: list[tuple[str, str]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if not _is_core_candidate(path):
            continue
        try:
            imports = _iter_forbidden_imports(path)
        except SyntaxError as exc:
            violations.append((str(path), f"SyntaxError: {exc}"))
            continue
        for imp in imports:
            violations.append((str(path), imp))

    if violations:
        sys.stderr.write("Qt import guard failed:\n")
        for file_path, imp in violations:
            sys.stderr.write(f"- {file_path}: {imp}\n")
        return 2

    print("Qt import guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
