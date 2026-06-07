"""Lightweight markdown quality checks for docs and README.

Non-exhaustive by design: fast, deterministic, and low-noise for CI gating.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path.cwd()
DOCS = sorted((ROOT / "docs").rglob("*.md"))
EXCLUDED_PREFIXES = (
    ROOT / "docs" / "_internal" / "archive",
    ROOT / "docs" / "_generated",
)
TARGETS = [ROOT / "README.md"] + [
    path
    for path in DOCS
    if not any(path.is_relative_to(prefix) for prefix in EXCLUDED_PREFIXES)
]
H1_RE = re.compile(r"^#\s+\S")
ALLOWED_ROOT_MARKDOWN = {"README.md"}


def main() -> int:
    """Run the main workflow."""
    failures: list[str] = []
    root_markdown = sorted(path.name for path in ROOT.glob("*.md"))
    unexpected_root_markdown = [
        name for name in root_markdown if name not in ALLOWED_ROOT_MARKDOWN
    ]
    if unexpected_root_markdown:
        failures.append(
            "root Markdown files must move under docs/: "
            + ", ".join(unexpected_root_markdown)
        )
    for path in TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        h1_count = 0
        in_fence = False
        for i, line in enumerate(lines, start=1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
            if "\t" in line:
                failures.append(f"{path}:L{i}: tab character not allowed")
            if line.rstrip() != line:
                failures.append(f"{path}:L{i}: trailing whitespace")
            if H1_RE.match(line):
                h1_count += 1
        if text and not text.endswith("\n"):
            failures.append(f"{path}: file must end with newline")
        if h1_count > 1:
            failures.append(f"{path}: multiple H1 headings ({h1_count})")
        if in_fence:
            failures.append(f"{path}: unclosed fenced code block")

    if failures:
        sys.stderr.write("Markdown quality checks failed:\n")
        for failure in failures:
            sys.stderr.write(f"  - {failure}\n")
        return 1

    print("Markdown quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
