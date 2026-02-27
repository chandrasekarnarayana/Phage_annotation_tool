"""Typed UI settings defaults and migration helpers."""

from __future__ import annotations

from typing import Any


UI_SETTINGS_DEFAULTS: dict[str, Any] = {
    "defaultLayoutPreset": "Default",
    "defaultColormap": "viridis",
    "defaultFPS": 10,
    "keepRecentImages": 10,
    "recentImages": [],
    "autosaveRecoveryEnabled": True,
    "autoLoadAnnotations": True,
    "applyAnnotationMetaOnLoad": False,
    "encodeAnnotationMetaFilename": False,
    "qcAutoShowOnIssues": True,
    "showRoiHandles": True,
}

LEGACY_KEY_MIGRATIONS: dict[str, str] = {
    "window_geometry": "customGeometry",
    "window_state": "customState",
}


def apply_settings_migrations(settings) -> None:
    """Copy known legacy keys forward when new keys are missing."""
    for legacy_key, current_key in LEGACY_KEY_MIGRATIONS.items():
        if settings.contains(current_key):
            continue
        if not settings.contains(legacy_key):
            continue
        value = settings.value(legacy_key, None)
        if value is not None:
            settings.setValue(current_key, value)

    # Normalize historical lowercase layout value used in older builds.
    layout = settings.value("defaultLayoutPreset", "Default", type=str)
    if str(layout).strip().lower() == "default":
        settings.setValue("defaultLayoutPreset", "Default")


def ensure_ui_settings_defaults(settings) -> None:
    """Seed deterministic defaults for key GUI settings."""
    for key, default in UI_SETTINGS_DEFAULTS.items():
        if not settings.contains(key):
            settings.setValue(key, default)
