"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_right_sidebar_rail_icons_toggle_exclusive_panels(qtbot, tmp_path):
    """Right icon rail should toggle target panels and keep assist details available."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_right_sidebar_rail.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    queue_act = win.findChild(QtWidgets.QAction, "right_sidebar_assist_toggle")
    qc_act = win.findChild(QtWidgets.QAction, "right_sidebar_qc_toggle")
    table_act = win.findChild(QtWidgets.QAction, "right_sidebar_table_toggle")
    advanced_act = win.findChild(QtWidgets.QAction, "right_sidebar_advanced_settings_toggle")
    assert queue_act is not None
    assert qc_act is not None
    assert table_act is not None
    assert advanced_act is not None
    assert win.findChild(QtWidgets.QAction, "right_sidebar_status_toggle") is None
    assert win.findChild(QtWidgets.QAction, "right_sidebar_relink_toggle") is None

    win.set_panel_visible("review_queue", False, source="test")
    win.set_panel_visible("annotations", False, source="test")
    win.set_panel_visible("advanced_settings", False, source="test")
    win.set_panel_visible("qc_issues", False, source="test")
    qtbot.wait(30)

    queue_act.trigger()
    qtbot.wait(30)
    assert win.dock_review_queue.isVisible()
    assert getattr(win, "review_queue_panel", None) is not None
    assert win.review_queue_panel.explain_panel.isVisible()

    queue_act.trigger()
    qtbot.wait(30)
    assert win.dock_review_queue.isVisible()

    advanced_act.trigger()
    qtbot.wait(30)
    assert win.dock_advanced_settings.isVisible()

    table_act.trigger()
    qtbot.wait(30)
    assert win.dock_annotations.isVisible()
    assert not win.dock_advanced_settings.isVisible()
    qtbot.wait(30)
    assert win.dock_annotations.isVisible()

    qc_act.trigger()
    qtbot.wait(30)
    assert win.dock_qc_issues.isVisible()

@pytest.mark.gui
def test_right_sidebar_panels_are_not_tabified(qtbot, tmp_path):
    """Inspect-side panels should behave as standalone panels, not tab peers."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_right_sidebar_no_tabs.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    inspect_docks = [
        getattr(win, "dock_annotations", None),
        getattr(win, "dock_review_queue", None),
        getattr(win, "dock_advanced_settings", None),
        getattr(win, "dock_advanced_analysis", None),
        getattr(win, "dock_qc_issues", None),
    ]
    inspect_docks = [d for d in inspect_docks if d is not None]

    for dock in inspect_docks:
        peers = set(win.tabifiedDockWidgets(dock) or [])
        assert not peers.intersection(set(inspect_docks) - {dock})

@pytest.mark.gui
def test_review_context_pack_hides_status_details(qtbot, tmp_path):
    """Review context pack should keep Status Details hidden for clutter control."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_review_pack_status_details.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.set_panel_visible("status_details", True, source="test")
    qtbot.wait(20)
    assert win.dock_status_details.isVisible()

    win._toggle_review_context_pack()
    qtbot.wait(20)
    assert not win.dock_status_details.isVisible()

@pytest.mark.gui
def test_left_sidebar_mode_switch_collapses_previous_context_docks(qtbot, tmp_path):
    """Switching left sidebar pages should collapse context docks from the previous mode."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_left_sidebar_mode_collapse.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    roi_idx = win._sidebar_action_index_for_label("ROI")
    annotate_idx = win._sidebar_action_index_for_label("Annotation")
    if roi_idx < 0 or annotate_idx < 0:
        pytest.skip("Sidebar mode labels unavailable")

    win._set_sidebar_mode(roi_idx)
    win.set_panel_visible("roi", True, source="test:auto")
    qtbot.wait(30)
    assert win.panel_docks["roi"].isVisible()

    win._set_sidebar_mode(annotate_idx)
    qtbot.wait(30)
    assert not win.panel_docks["roi"].isVisible()

@pytest.mark.gui
def test_sidebar_workflow_pages_apply_supporting_dock_defaults(qtbot, tmp_path):
    """Workflow pages should surface their intended supporting docks by default."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_sidebar_workflow_defaults.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    annotate_idx = win._sidebar_action_index_for_label("Annotation")
    contrast_idx = win._sidebar_action_index_for_label("Contrast")
    lazy_idx = win._sidebar_action_index_for_label("Lazy Loading")
    roi_idx = win._sidebar_action_index_for_label("ROI")
    if annotate_idx < 0 or contrast_idx < 0 or lazy_idx < 0 or roi_idx < 0:
        pytest.skip("Workflow sidebar labels unavailable")

    win._set_sidebar_mode(annotate_idx)
    qtbot.wait(30)
    assert win.dock_annotations.isVisible(), "Annotation should surface the annotation table"

    win._set_sidebar_mode(contrast_idx)
    qtbot.wait(30)
    assert win.panel_docks["hist"].isVisible(), "Contrast should surface histogram"

    win._set_sidebar_mode(lazy_idx)
    qtbot.wait(30)
    assert win.panel_docks["hist"].isVisible(), "Lazy Loading should surface histogram"

    win._set_sidebar_mode(roi_idx)
    qtbot.wait(30)
    assert win.roi_x_spin.isVisible(), "ROI should surface ROI controls"

@pytest.mark.gui
def test_prepare_page_exposes_setup_context_and_live_summaries(qtbot, tmp_path):
    """Lazy Loading page should expose loading and sync summaries."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_prepare_page_setup_context.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    prepare_idx = win._sidebar_action_index_for_label("Lazy Loading")
    if prepare_idx < 0:
        pytest.skip("Lazy Loading sidebar label unavailable")

    win._set_sidebar_mode(prepare_idx)
    qtbot.wait(30)

    assert not hasattr(win, "primary_combo"), "Lazy Loading should not expose legacy primary selectors"
    assert not hasattr(win, "support_combo"), "Lazy Loading should not expose legacy support selectors"
    assert hasattr(win, "prepare_reference_summary_lbl")
    assert hasattr(win, "prepare_sync_target_lbl")
    assert hasattr(win, "prepare_sync_contract_lbl")
    assert hasattr(win, "prepare_sync_panels_lbl")
    assert win.prepare_reference_summary_lbl.text().startswith("Reference views:")
    assert win.prepare_sync_target_lbl.text().startswith("Sync target:")
    assert win.prepare_sync_contract_lbl.text().startswith("Sync contract:")
    assert win.prepare_sync_panels_lbl.text().startswith("Sync panels:")

@pytest.mark.gui
def test_roi_dock_is_helper_surface_not_primary_editor(qtbot, tmp_path):
    """ROI dock should redirect to ROI page instead of hosting a second ROI editor."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtWidgets
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_roi_dock_helper.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.open_panel("roi", reason="test")
    qtbot.wait(30)

    dock = win.panel_docks["roi"]
    widget = dock.widget()
    labels = [child.text() for child in widget.findChildren(QtWidgets.QLabel)]
    buttons = {child.text(): child for child in widget.findChildren(QtWidgets.QPushButton)}

    assert any("ROI page" in text for text in labels)
    assert "Open ROI Page" in buttons
    assert "Open ROI Manager" in buttons
    assert "Clear ROI" in buttons
    assert not any(text == "ROI X" for text in labels), "ROI dock should not host a second live ROI editor"

@pytest.mark.gui
def test_sidebar_collapses_to_five_workflow_pages(qtbot, tmp_path):
    """The workflow sidebar should expose the consolidated 4-page taxonomy."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_sidebar_five_pages.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    labels = [str(act.text()) for act in getattr(win, "sidebar_actions", []) or []]
    assert labels == [
        "Lazy Loading",
        "Annotation",
        "ROI",
        "Contrast",
    ]
    assert win._sidebar_action_index_for_label("Preferences") == -1
    assert win._sidebar_action_index_for_label("Measurements") == -1
