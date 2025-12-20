"""Guard against Qt imports in core modules.

Run this script in CI or locally to ensure core modules remain Qt-free.
"""

from __future__ import annotations

from pathlib import Path
import sys


CORE_MODULES = [
    "src/phage_annotator/io.py",
    "src/phage_annotator/analysis.py",
    "src/phage_annotator/annotations.py",
    "src/phage_annotator/project_io.py",
    "src/phage_annotator/projection_cache.py",
    "src/phage_annotator/pyramid.py",
    "src/phage_annotator/ring_buffer.py",
]

FORBIDDEN = ("PyQt", "PySide", "QtCore", "QtWidgets")


def main() -> int:
    bad = []
    for rel in CORE_MODULES:
        path = Path(rel)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN:
            if token in text:
                bad.append(f"{rel} contains '{token}'")
                break
    if bad:
        sys.stderr.write("Qt import guard failed:\n")
        sys.stderr.write("\n".join(bad))
        sys.stderr.write("\n")
        return 2
    print("Qt import guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
