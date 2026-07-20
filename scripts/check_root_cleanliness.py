#!/usr/bin/env python3
"""Ensure the repository root only contains intentional top-level files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()
ALLOWED_ROOT_FILES = {
    ".dockerignore",
    ".gitignore",
    "docker-compose.yml",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "pyproject.toml",
}
ALLOWED_ROOT_DIRS = {
    ".agents",
    ".codex",
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv-phage",
    "data",
    "docs",
    "external_plugins",
    "project",
    "scripts",
    "src",
    "tests",
}


def _tracked_root_files() -> list[str]:
    """Handle the tracked root files helper flow."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        line
        for line in result.stdout.splitlines()
        if line and "/" not in line and (ROOT / line).exists()
    )


def main() -> int:
    """Validate root-level tracked files and visible filesystem entries."""
    failures: list[str] = []

    unexpected_tracked = [
        name for name in _tracked_root_files() if name not in ALLOWED_ROOT_FILES
    ]
    if unexpected_tracked:
        failures.append(
            "tracked root files must move into a purpose folder: "
            + ", ".join(unexpected_tracked)
        )

    for path in sorted(ROOT.iterdir()):
        name = path.name
        if path.is_file() and name not in ALLOWED_ROOT_FILES:
            failures.append(f"unexpected root file: {name}")
        elif path.is_dir() and name not in ALLOWED_ROOT_DIRS:
            failures.append(f"unexpected root directory: {name}")

    if failures:
        sys.stderr.write("Root cleanliness check failed:\n")
        for failure in failures:
            sys.stderr.write(f"  - {failure}\n")
        return 1

    print("Root cleanliness check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
