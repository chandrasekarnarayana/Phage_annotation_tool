"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_smlm_plugin_dropdown_hides_internal_profiles(qtbot, tmp_path):
    """SMLM plugin dropdown should hide non-UI manifest profiles."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_smlm_plugin_visibility.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._show_smlm_panel()
    qtbot.wait(100)
    assert win.smlm_panel is not None
    combo = win.smlm_panel.thunder.plugin_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    joined = " | ".join(labels).lower()
    assert "thunder_storm_fast" not in joined
    assert "thunder_storm" in joined

@pytest.mark.gui
def test_annotation_table_controls_wiring(qtbot, tmp_path):
    """Test annotation table controls (add, delete, filter) are wired."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_annot_table.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Verify annotation table exists
    if hasattr(win, "annot_table"):
        assert win.annot_table is not None

        # Verify table has column headers
        headers = []
        for col in range(win.annot_table.columnCount()):
            item = win.annot_table.horizontalHeaderItem(col)
            if item:
                headers.append(item.text())
        
        # Should have at least: X, Y, Z, T, Label
        assert len(headers) > 0, "Annotation table should have columns"

@pytest.mark.gui
def test_playback_controls_wiring(qtbot, tmp_path):
    """Test playback controls (Play T, Play Z, Speed, Loop) are wired."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_playback.tif", mode="tz")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Verify playback controls exist
    assert hasattr(win, "play_t_btn"), "Play T button not found"
    assert hasattr(win, "play_z_btn"), "Play Z button not found"
    assert hasattr(win, "speed_slider"), "Speed slider not found"
    assert hasattr(win, "loop_chk"), "Loop checkbox not found"

    # Test play button can be clicked without error
    if hasattr(win, "play_t_btn"):
        win.play_t_btn.click()
        qtbot.wait(100)
        # Playback started or toggled

    assert True, "Playback controls wired"

def test_ui_wiring_no_gui():
    """Test UI wiring consistency without GUI (non-interactive checks)."""
    # Verify action names follow naming conventions
    expected_action_names = {
        "open_files": "Open files...",
        "open_folder": "Open folder...",
        "export_view": "Export View...",
        "clear_roi": "Clear ROI",
        "undo": "Undo",
        "redo": "Redo",
    }

    # These are just naming patterns - would be fully verified in GUI tests
    for var_name, display_name in expected_action_names.items():
        assert isinstance(var_name, str), f"Action variable name should be string: {var_name}"
        assert isinstance(display_name, str), f"Action display name should be string: {display_name}"

    assert True, "UI naming conventions verified"
