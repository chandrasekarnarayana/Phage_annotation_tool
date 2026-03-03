"""Tests for declared console script entrypoints in pyproject."""

from __future__ import annotations

import re
from pathlib import Path


def test_required_console_entrypoints_declared() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    block_match = re.search(r"(?ms)^\[project\.scripts\]\n(.*?)(?:^\[|\Z)", pyproject)
    assert block_match, "Missing [project.scripts] block in pyproject.toml"
    scripts_block = block_match.group(1)
    declared = {}
    for line in scripts_block.splitlines():
        row = line.strip()
        if not row or row.startswith("#") or "=" not in row:
            continue
        key, value = row.split("=", 1)
        declared[key.strip()] = value.strip().strip('"').strip("'")
    required = {
        "phage-annotator": "phage_annotator.cli:main",
        "phage-annotator-smlm-preflight": "phage_annotator.smlm.preflight_cli:main",
        "phage-annotator-smlm-parity": "phage_annotator.smlm.parity_cli:main",
        "phage-annotator-smlm-run-demo": "phage_annotator.smlm.demo_cli:main",
        "phage-annotator-fiji-plugin-tool": "phage_annotator.smlm.external_plugins_cli:main",
    }
    missing = [name for name in required if name not in declared]
    assert not missing, f"Missing console entrypoints: {missing}"
    for name, target in required.items():
        assert declared[name] == target
