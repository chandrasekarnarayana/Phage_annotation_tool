"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_panel_auto_open_policy_can_block_auto_reason(qtbot, tmp_path):
    """Auto-open reasons should respect per-panel auto-open policy."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_auto_policy.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    win.set_panel_visible(panel_id, False, source="test")
    qtbot.wait(20)
    assert not win.panel_docks[panel_id].isVisible()

    win.set_panel_auto_open_enabled(panel_id, False)
    win.open_panel(panel_id, reason="job:auto_error")
    qtbot.wait(20)
    assert not win.panel_docks[panel_id].isVisible()

    win.open_panel(panel_id, reason="user")
    qtbot.wait(20)
    assert win.panel_docks[panel_id].isVisible()

@pytest.mark.gui
def test_panel_open_source_and_pin_tracking(qtbot, tmp_path):
    """Panel switcher should track opened-by source and pin explicit user opens."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_open_tracking.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    win.set_panel_visible(panel_id, False, source="test")
    qtbot.wait(10)
    win.set_panel_auto_open_enabled(panel_id, True)
    win.set_panel_pinned(panel_id, False)
    assert not win.is_panel_pinned(panel_id)

    win.open_panel(panel_id, reason="job:auto_error")
    qtbot.wait(20)
    assert win.get_panel_opened_by(panel_id) == "auto"
    assert not win.is_panel_pinned(panel_id)

    win.open_panel(panel_id, reason="menu:view")
    qtbot.wait(20)
    assert win.get_panel_opened_by(panel_id) == "user"
    assert win.is_panel_pinned(panel_id)

@pytest.mark.gui
def test_panel_auto_open_trigger_disabled_blocks_matching_trigger(qtbot, tmp_path):
    """Per-trigger auto-open policy should block matching auto reasons."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_auto_trigger_disabled.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    trigger = "roi_mode"
    win.set_panel_visible(panel_id, False, source="test")
    win.set_panel_auto_open_enabled(panel_id, True)
    win.set_panel_auto_open_enabled_for_trigger(panel_id, trigger, False)

    win.open_panel(panel_id, reason=f"auto:{trigger}")
    qtbot.wait(20)
    assert not win.panel_docks[panel_id].isVisible()

@pytest.mark.gui
def test_panel_auto_open_trigger_enabled_allows_matching_trigger(qtbot, tmp_path):
    """Per-trigger auto-open policy should allow matching auto reasons when enabled."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_auto_trigger_enabled.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    trigger = "review_mode"
    win.set_panel_visible(panel_id, False, source="test")
    win.set_panel_auto_open_enabled(panel_id, True)
    win.set_panel_auto_open_enabled_for_trigger(panel_id, trigger, True)

    win.open_panel(panel_id, reason=f"auto:{trigger}")
    qtbot.wait(20)
    assert win.panel_docks[panel_id].isVisible()

@pytest.mark.gui
def test_panel_auto_open_trigger_policy_persists_after_reload(qtbot, tmp_path):
    """Per-trigger auto-open preference should persist across window reloads."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_auto_trigger_persist.tif", mode="2d")
    panel_id = "advanced_analysis"
    trigger = "roi_mode"

    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.set_panel_auto_open_enabled(panel_id, True)
    win.set_panel_auto_open_enabled_for_trigger(panel_id, trigger, False)
    qtbot.wait(20)
    win.close()
    qtbot.wait(20)

    win2 = create_app([path])
    qtbot.addWidget(win2)
    win2.show()
    qtbot.waitExposed(win2)
    assert not win2.is_panel_auto_open_enabled_for_trigger(panel_id, trigger)
    win2.set_panel_visible(panel_id, False, source="test")
    win2.open_panel(panel_id, reason=f"auto:{trigger}")
    qtbot.wait(20)
    assert not win2.panel_docks[panel_id].isVisible()

@pytest.mark.gui
def test_open_panel_policy_action_navigates_preferences(qtbot, tmp_path):
    """Layout action should jump to Preferences panel-policy section."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_policy_nav.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    assert getattr(win, "open_panel_policy_act", None) is not None
    win.open_panel_policy_act.trigger()
    qtbot.wait(40)

    assert getattr(win, "panel_policy_group", None) is not None
    assert win.panel_policy_group.isVisible()
    assert win.panel_policy_group.hasFocus() or getattr(win, "panel_policy_reset_btn", None) is not None

@pytest.mark.gui
def test_panel_policy_controls_update_switcher_state(qtbot, tmp_path):
    """Panel-policy checkboxes should drive persisted auto-open and pin state."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_panel_policy_controls.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    auto_chk = win.panel_policy_auto_checks.get(panel_id)
    pin_chk = win.panel_policy_pin_checks.get(panel_id)
    assert auto_chk is not None
    assert pin_chk is not None

    auto_chk.setChecked(False)
    qtbot.wait(20)
    assert not win.is_panel_auto_open_enabled(panel_id)

    pin_chk.setChecked(True)
    qtbot.wait(20)
    assert win.is_panel_pinned(panel_id)

@pytest.mark.gui
def test_layout_panels_quick_policy_menu_updates_state(qtbot, tmp_path):
    """Quick policy actions in Layout->Panels should update panel policy state."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_quick_policy_menu.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    panel_id = "advanced_analysis"
    auto_act = win.findChild(QtWidgets.QAction, f"panel_policy_auto_{panel_id}")
    pin_act = win.findChild(QtWidgets.QAction, f"panel_policy_pin_{panel_id}")
    open_act = win.findChild(QtWidgets.QAction, f"panel_policy_open_{panel_id}")
    assert auto_act is not None
    assert pin_act is not None
    assert open_act is not None

    auto_act.setChecked(False)
    qtbot.wait(20)
    assert not win.is_panel_auto_open_enabled(panel_id)

    pin_act.setChecked(True)
    qtbot.wait(20)
    assert win.is_panel_pinned(panel_id)

    win.set_panel_visible(panel_id, False, source="test")
    qtbot.wait(20)
    open_act.trigger()
    qtbot.wait(20)
    assert win.panel_docks[panel_id].isVisible()
