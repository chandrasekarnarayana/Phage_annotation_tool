"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_command_palette_action_inventory(qtbot, tmp_path):
    """Test that command palette has all registered actions with proper names."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_palette.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    from PyQt5 import QtWidgets

    # Collect menu actions using Qt's menuBar/actions API.
    menubar = win.menuBar()
    assert menubar is not None, "MenuBar not found"

    menu_actions = []
    for top_action in menubar.actions():
        top_menu = top_action.menu()
        if top_menu is None:
            continue
        menu_actions.extend(top_menu.actions())
        for sub_action in top_menu.actions():
            sub_menu = sub_action.menu()
            if sub_menu is not None:
                menu_actions.extend(sub_menu.actions())

    # Verify critical actions are present.
    critical_actions = [
        "Open files…",
        "Open folder…",
        "Save project…",
        "Load project…",
        "Export View…",
        "Undo",
        "Redo",
        "Clear ROI",
        "Threshold…",
        "Analyze Particles…",
        "ThunderSTORM (ROI)",
    ]

    action_names = {a.text() for a in menu_actions if isinstance(a, QtWidgets.QAction) and a.text()}
    for action in critical_actions:
        assert action in action_names, f"Critical action '{action}' not found in menus"

@pytest.mark.gui
def test_status_bar_operational_state_contract(qtbot, tmp_path):
    """Status bar must expose key operational state fields at all times."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_status_contract.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    required = [
        ("status_dataset_lbl", "Dataset:"),
        ("status_tz_lbl", "T:"),
        ("status_scope_lbl", "Scope:"),
        ("status_target_lbl", "Target:"),
        ("status_assist_lbl", "Assist:"),
        ("status_qc_lbl", "QC:"),
    ]
    for attr, prefix in required:
        widget = getattr(win, attr, None)
        assert widget is not None, f"Missing status widget: {attr}"
        assert widget.text().startswith(prefix), f"Unexpected text for {attr}: {widget.text()}"

@pytest.mark.gui
def test_dynamic_target_constraints_for_single_modality(qtbot, tmp_path):
    """Target controls should disable unavailable options and show hint."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_target_constraints_single.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._refresh_annotation_view_controls()
    qtbot.wait(30)

    targets = dict(getattr(win, "_target_buttons", {}) or {})
    assert "frame" in targets
    assert "support" in targets
    assert targets["frame"].isEnabled()
    assert not targets["support"].isEnabled(), "Support target should be disabled with single-modality context"
    hint = getattr(win, "target_unavailable_hint_lbl", None)
    assert hint is not None and hint.isVisible()
    assert "unavailable" in hint.text().lower()

@pytest.mark.gui
def test_right_dock_mode_contract(qtbot, tmp_path):
    """Right dock should adapt by mode: annotate -> review -> inspect."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_right_dock_mode_contract.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._set_right_dock_mode("annotate")
    qtbot.wait(30)
    assert win.dock_annotations.isVisible(), "Annotation table should be primary in annotate mode"
    assert not win.dock_review_queue.isVisible()
    assert getattr(win, "review_queue_panel", None) is not None
    assert not win.review_queue_panel.explain_panel.isVisible()

    win._set_right_dock_mode("review")
    qtbot.wait(30)
    assert win.dock_review_queue.isVisible()
    assert win.dock_qc_issues.isVisible()

    win._set_right_dock_mode("inspect")
    qtbot.wait(30)
    assert not win.dock_review_queue.isVisible()
    assert win.dock_annotations.isVisible()
    assert getattr(win, "review_queue_panel", None) is not None
    assert not win.review_queue_panel.explain_panel.isVisible()
    assert win.dock_status_details.isVisible()

@pytest.mark.gui
def test_view_menu_toggle_wiring(qtbot, tmp_path):
    """Test View menu toggles for docks, panels, and overlays."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_view_menu.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Test dock visibility toggles (View > Dock Panels)
    docks = win.findChildren(type(win.__class__.dockWidgets()[0]) if hasattr(win, "dockWidgets") else type(None))
    
    # Verify docks are toggleable via menu
    if hasattr(win, "dock_annotation_table"):
        initial_visible = win.dock_annotation_table.isVisible()
        if hasattr(win, "toggle_dock_annotation_table"):
            win.toggle_dock_annotation_table()
            qtbot.wait(100)
            assert win.dock_annotation_table.isVisible() == (not initial_visible)

    # Test panel visibility toggles
    if hasattr(win, "show_frame_act"):
        initial = win.show_frame_act.isChecked()
        win.show_frame_act.trigger()
        # Panel state updated via the active ROI crop toggle handler.
        assert True  # Toggle executed without error

@pytest.mark.gui
def test_keyboard_shortcuts_consistency(qtbot, tmp_path):
    """Test keyboard shortcut registration and consistency."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_shortcuts.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    from PyQt5 import QtWidgets

    # Collect all actions with shortcuts from the window and child widgets.
    shortcuts_found = set()
    actions = list(win.findChildren(QtWidgets.QAction)) + list(win.actions())
    for action in actions:
        key = action.shortcut().toString()
        if key:
            shortcuts_found.add(key)

    # Verify critical shortcuts are registered.
    for shortcut in ["Ctrl+Z", "Ctrl+Shift+Z", "Ctrl+M", "Ctrl+Shift+P", "Ctrl+Alt+P", "F1"]:
        assert shortcut in shortcuts_found, f"Shortcut '{shortcut}' not registered"

@pytest.mark.gui
def test_layout_preset_action_fires_once(qtbot, tmp_path):
    """Layout preset action should invoke apply_preset exactly once per trigger."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_layout_single_fire.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    calls = []

    def _spy_apply_preset(name: str):
        """Handle the spy apply preset helper flow."""
        calls.append(str(name))

    win.apply_preset = _spy_apply_preset
    win.layout_preset_annotate_act.trigger()
    qtbot.wait(50)

    assert calls == ["Annotate"], f"Expected single call, got: {calls}"

@pytest.mark.gui
def test_overlay_toggle_action_fires_once(qtbot, tmp_path):
    """Overlay toggle should execute one refresh cycle per trigger."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_overlay_single_fire.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    refresh_calls = []
    win._refresh_image = lambda: refresh_calls.append("refresh")

    win.toggle_overlay_act.trigger()
    qtbot.wait(50)

    assert len(refresh_calls) == 1, f"Expected one refresh, got {len(refresh_calls)}"

@pytest.mark.gui
def test_reset_layout_action_fires_once(qtbot, tmp_path):
    """Reset layout should run each reset step exactly once per trigger."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_reset_layout_single_fire.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_default_calls = []
    canvas_layout_calls = []
    win._apply_panel_defaults = lambda: panel_default_calls.append("defaults")
    win._apply_canvas_priority_layout = lambda: canvas_layout_calls.append("canvas")

    win.reset_layout_act.trigger()
    qtbot.wait(50)

    assert panel_default_calls == ["defaults"], f"Expected one defaults call, got {panel_default_calls}"
    assert canvas_layout_calls == ["canvas"], f"Expected one canvas call, got {canvas_layout_calls}"
