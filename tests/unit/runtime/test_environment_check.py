"""Unit tests for startup environment manifest validation."""

from __future__ import annotations

from pathlib import Path

from phage_annotator.runtime.environment_check import check_environment


def test_environment_check_reports_missing_manifest(tmp_path: Path) -> None:
    """Verify environment check reports missing manifest for the current workflow."""
    result = check_environment(tmp_path / "missing.yml", emit_warnings=False)
    assert result.missing_manifest is True
    assert result.warnings


def test_environment_check_accepts_current_python(tmp_path: Path) -> None:
    """Verify environment check accepts current python for the current workflow."""
    manifest = tmp_path / "environment.yml"
    manifest.write_text(
        "name: test\nchannels:\n  - conda-forge\ndependencies:\n  - python>=3.1\n",
        encoding="utf-8",
    )
    result = check_environment(manifest, emit_warnings=False)
    assert result.ok


def test_environment_check_falls_back_to_cwd_manifest(tmp_path: Path, monkeypatch) -> None:
    """Verify environment check falls back to cwd manifest for the current workflow."""
    manifest_dir = tmp_path / "project"
    manifest_dir.mkdir()
    manifest = manifest_dir / "environment.yml"
    manifest.write_text("dependencies:\n  - python>=3.1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = check_environment(Path("/missing/environment.yml"), emit_warnings=False)

    assert result.ok
    assert result.manifest_path == manifest
