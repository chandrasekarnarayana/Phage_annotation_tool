"""Release hygiene checks for tracked artifacts.

Checks:
- no tracked .egg-info files
- no oversized tracked files beyond threshold (except allowlist)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


MAX_TRACKED_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWLIST = {
    # Keep empty by default; add deliberate exceptions only when justified.
}
IGNORE_PREFIXES = (
    ".venv/",
    ".venv-",
    "build/",
    "artifacts/",
)


def _tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(line.strip()) for line in proc.stdout.splitlines() if line.strip()]


def main() -> int:
    root = Path.cwd()
    bad_generated: list[str] = []
    bad_large: list[str] = []

    for rel in _tracked_files():
        rel_posix = rel.as_posix()
        if rel_posix.startswith(IGNORE_PREFIXES):
            continue
        if rel_posix.endswith(".egg-info") or ".egg-info/" in rel_posix:
            bad_generated.append(rel_posix)
            continue
        if rel_posix in ALLOWLIST:
            continue
        path = root / rel
        if not path.exists():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > MAX_TRACKED_BYTES:
            bad_large.append(f"{rel_posix} ({size / (1024 * 1024):.1f} MB)")

    if bad_generated or bad_large:
        sys.stderr.write("Release hygiene checks failed.\n")
        if bad_generated:
            sys.stderr.write("\nTracked generated artifacts (.egg-info):\n")
            for item in bad_generated:
                sys.stderr.write(f"  - {item}\n")
        if bad_large:
            sys.stderr.write("\nOversized tracked files (>20 MB):\n")
            for item in bad_large:
                sys.stderr.write(f"  - {item}\n")
        return 1

    print("Release hygiene checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
