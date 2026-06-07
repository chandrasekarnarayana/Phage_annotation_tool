"""Tests for the centralized keyboard shortcut registry."""

from __future__ import annotations

from phage_annotator.ui_qt.keyboard_registry import (
    all_shortcuts,
    detect_conflicts,
    qt_key_bindings,
)
import pytest


def test_registry_has_no_conflicts() -> None:
    """Verify registry has no conflicts for the current workflow."""
    assert detect_conflicts(all_shortcuts()) == []


def test_assist_navigation_shortcuts_present() -> None:
    """Verify assist navigation shortcuts present for the current workflow."""
    by_id = {entry.id: entry for entry in all_shortcuts()}
    assert by_id["accept_suggestion"].shortcut == "A"
    assert by_id["reject_suggestion"].shortcut == "R"
    assert by_id["next_suggestion"].shortcut == "N"
    assert by_id["prev_suggestion"].shortcut == "P"


def test_help_shortcut_has_menu_action_binding() -> None:
    """Verify help shortcut has menu action binding for the current workflow."""
    by_id = {entry.id: entry for entry in all_shortcuts()}
    assert by_id["help_shortcuts"].menu_action_attr == "shortcuts_act"


def test_qt_bindings_distinguish_reject_vs_clear_roi() -> None:
    """Verify qt bindings distinguish reject vs clear roi for the current workflow."""
    if not qt_key_bindings():
        pytest.skip("Qt bindings unavailable in headless test environment.")
    bindings = {(key, int(mods)): action for key, mods, action in qt_key_bindings()}
    reject = [action for action in bindings.values() if action == "reject_suggestion"]
    clear = [action for action in bindings.values() if action == "clear_roi"]
    assert reject
    assert clear
