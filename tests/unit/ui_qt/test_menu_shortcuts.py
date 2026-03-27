"""Menu-shortcut policy tests."""

from phage_annotator.ui_qt.keyboard_registry import all_shortcuts, detect_conflicts


def test_menu_shortcuts_have_no_conflicts() -> None:
    """Global shortcut registry should not assign duplicate sequences."""
    assert detect_conflicts(all_shortcuts()) == []


def test_menu_shortcuts_cover_core_menu_actions() -> None:
    """Core menu actions should use standard, discoverable shortcuts."""
    by_id = {entry.id: entry for entry in all_shortcuts()}

    assert by_id["open_files"].shortcut == "Ctrl+O"
    assert by_id["save_project"].shortcut == "Ctrl+S"
    assert by_id["save_annotations_csv"].shortcut == "Ctrl+Shift+S"
    assert by_id["preferences"].shortcut == "Ctrl+,"
    assert by_id["export_view"].shortcut == "Ctrl+E"
    assert by_id["validate_qc"].shortcut == "Ctrl+Shift+Q"
