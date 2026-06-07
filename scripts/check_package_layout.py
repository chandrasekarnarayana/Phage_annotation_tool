#!/usr/bin/env python3
"""Validate the top-level package layout after facade removal."""

from __future__ import annotations

from pathlib import Path
import sys


PKG_ROOT = Path(__file__).resolve().parents[1] / "src" / "phage_annotator"

ALLOWED_ROOT_PY_FILES = {
    "__init__.py",
    "__main__.py",
    "cli.py",
    "demo.py",
}

REQUIRED_PACKAGE_DIRS = {
    "algorithms",
    "analysis",
    "annotation",
    "cache",
    "config",
    "constants",
    "core",
    "data",
    "deepstorm",
    "density",
    "framework",
    "io",
    "plugins",
    "rendering",
    "roi",
    "runtime",
    "session",
    "smlm",
    "tools",
    "ui_qt",
    "utils",
}

LEGACY_FACADE_MODULES = {
    "analysis.py",
    "array_pool.py",
    "auto_roi.py",
    "calibration.py",
    "config.py",
    "coordinate_transforms.py",
    "density_config.py",
    "density_infer.py",
    "density_model.py",
    "disk_cache.py",
    "export_view.py",
    "gui_actions.py",
    "gui_annotations.py",
    "gui_constants.py",
    "gui_controls.py",
    "gui_controls_density.py",
    "gui_controls_display.py",
    "gui_controls_preferences.py",
    "gui_controls_recorder.py",
    "gui_controls_results.py",
    "gui_controls_roi.py",
    "gui_controls_smlm.py",
    "gui_controls_threshold.py",
    "gui_debug.py",
    "gui_events.py",
    "gui_export.py",
    "gui_file_actions.py",
    "gui_image_io.py",
    "gui_jobs.py",
    "gui_mpl.py",
    "gui_playback.py",
    "gui_rendering.py",
    "gui_roi_crop.py",
    "gui_state.py",
    "gui_table_status.py",
    "gui_ui_extra.py",
    "gui_ui_setup.py",
    "keyboard_shortcuts_dialog.py",
    "logger.py",
    "metadata_dock.py",
    "orthoview.py",
    "panels.py",
    "particles.py",
    "performance_panel.py",
    "project_io.py",
    "projection_cache.py",
    "pyramid.py",
    "recorder.py",
    "results_table.py",
    "ring_buffer.py",
    "roi_widgets.py",
    "scalebar.py",
    "smlm_ui.py",
    "smlm_widget.py",
    "stale_result_guard.py",
    "threshold_panel.py",
    "thresholding.py",
}


def main() -> int:
    """Run the main workflow."""
    issues: list[str] = []
    root_py_files = sorted(path.name for path in PKG_ROOT.glob("*.py"))

    unexpected_root_py = [name for name in root_py_files if name not in ALLOWED_ROOT_PY_FILES]
    missing_root_py = sorted(ALLOWED_ROOT_PY_FILES.difference(root_py_files))

    if unexpected_root_py:
        issues.append(
            "Unexpected root-level python modules found: " + ", ".join(unexpected_root_py)
        )
    if missing_root_py:
        issues.append("Missing required root-level modules: " + ", ".join(missing_root_py))

    present_facades = sorted(name for name in LEGACY_FACADE_MODULES if (PKG_ROOT / name).exists())
    if present_facades:
        issues.append("Legacy facade modules should stay removed: " + ", ".join(present_facades))

    for package_name in sorted(REQUIRED_PACKAGE_DIRS):
        package_dir = PKG_ROOT / package_name
        init_file = package_dir / "__init__.py"
        if not package_dir.is_dir():
            issues.append(f"Missing required package directory: {package_name}")
            continue
        if not init_file.exists():
            issues.append(f"Missing package initializer: {package_name}/__init__.py")

    if issues:
        sys.stderr.write("Package layout check failed:\n")
        for issue in issues:
            sys.stderr.write(f"- {issue}\n")
        return 1

    print("Package layout check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
