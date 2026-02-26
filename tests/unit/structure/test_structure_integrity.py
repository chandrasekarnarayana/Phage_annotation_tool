"""Structure integrity tests for package reorganization."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src" / "phage_annotator"

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
    "cli.py",
    "demo.py",
}


def _iter_source_modules() -> list[tuple[str, Path]]:
    modules: list[tuple[str, Path]] = []
    for py_file in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        rel = py_file.relative_to(SRC_ROOT)
        if rel.name == "__init__.py":
            module = "phage_annotator" + ("." + ".".join(rel.parent.parts) if rel.parent.parts else "")
        else:
            module = "phage_annotator." + ".".join(rel.with_suffix("").parts)
        modules.append((module, py_file))
    return modules


def _is_headless_candidate(path: Path) -> bool:
    rel = path.relative_to(SRC_ROOT)
    if rel.parts and rel.parts[0] in HEADLESS_PACKAGES:
        return True
    return len(rel.parts) == 1 and rel.name in HEADLESS_ROOT_MODULES


def _run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script_name)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_import_integrity_script_passes() -> None:
    """All internal package imports should resolve."""
    result = _run_script("check_import_integrity.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_core_no_qt_script_passes() -> None:
    """Core/headless modules should stay free of Qt dependencies."""
    result = _run_script("check_core_no_qt.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_package_layout_script_passes() -> None:
    """Top-level package layout should stay in the post-facade state."""
    result = _run_script("check_package_layout.py")
    assert result.returncode == 0, result.stdout + result.stderr


def test_non_gui_modules_import_cleanly() -> None:
    """All non-GUI modules should import without runtime errors."""
    failures: list[tuple[str, str]] = []
    for module_name, path in _iter_source_modules():
        if not _is_headless_candidate(path):
            continue
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - exercised via failing environments
            failures.append((module_name, repr(exc)))

    assert not failures, "Import failures:\n" + "\n".join(
        f"- {module}: {error}" for module, error in failures
    )
