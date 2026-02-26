"""Unit tests for constants/settings defaults and package exports."""

from __future__ import annotations

import phage_annotator.constants as constants
import phage_annotator.constants.settings as settings


def test_settings_get_default_returns_known_and_fallback_values() -> None:
    """Known keys should resolve; unknown keys should return provided fallback."""
    assert settings.get_default(settings.MARKER_SIZE) == settings.MARKER_SIZE_DEFAULT
    assert settings.get_default("unknown", fallback="x") == "x"


def test_settings_defaults_dictionary_contains_key_constants() -> None:
    """DEFAULTS should include main rendering/cache settings keys."""
    keys = settings.DEFAULTS.keys()
    assert settings.MARKER_SIZE in keys
    assert settings.CACHE_MAX_MB in keys
    assert settings.PYRAMID_ENABLED in keys
    assert settings.SCALE_BAR_ENABLED in keys


def test_constants_package_reexports_settings_symbols() -> None:
    """Package-level constants should stay aligned with settings module values."""
    assert constants.MARKER_SIZE == settings.MARKER_SIZE
    assert constants.MARKER_SIZE_DEFAULT == settings.MARKER_SIZE_DEFAULT
    assert constants.CACHE_MAX_MB_DEFAULT == settings.CACHE_MAX_MB_DEFAULT
    assert constants.get_default(settings.DEFAULT_LAYOUT_PRESET) == "default"
