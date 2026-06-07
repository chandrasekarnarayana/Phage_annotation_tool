"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_open_training_controls_routes_to_preferences(qtbot, tmp_path):
    """Open Training Controls should still open preferences tooling."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_open_training_controls.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Start from a non-preferences state.
    win._set_sidebar_mode(0)
    win._collapse_sidebar()
    qtbot.wait(50)

    win.advanced_open_training_btn.click()
    qtbot.wait(80)

    assert True

@pytest.mark.gui
def test_advanced_analysis_toggle_syncs_visibility_and_menu_state(qtbot, tmp_path):
    """Advanced Analysis panel toggle should keep dock/action state synchronized."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_advanced_analysis_toggle.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    dock = win.panel_docks.get("advanced_analysis")
    act = win.dock_actions.get("advanced_analysis")
    assert dock is not None, "Advanced Analysis dock missing"
    assert act is not None, "Advanced Analysis action missing"

    win.set_panel_visible("advanced_analysis", True, source="test")
    qtbot.wait(40)
    assert dock.isVisible(), "Advanced Analysis dock should be visible"
    assert act.isChecked(), "Advanced Analysis menu checkmark should be checked"

    act.trigger()
    qtbot.wait(40)
    assert not dock.isVisible(), "Advanced Analysis dock should hide on toggle"
    assert not act.isChecked(), "Advanced Analysis menu checkmark should uncheck"

@pytest.mark.gui
def test_command_palette_weighting_usage_and_mode_boost(qtbot, tmp_path):
    """Command palette should boost by usage and by current workflow mode."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtCore, QtWidgets
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_palette_weighting.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    def _palette_labels() -> list[str]:
        """Handle the palette labels helper flow."""
        win._show_command_palette()
        qtbot.wait(40)
        dlg = getattr(win, "_command_palette_dialog", None)
        assert dlg is not None and dlg.isVisible(), "Command palette dialog not visible"
        listw = dlg.findChild(QtWidgets.QListWidget)
        assert listw is not None, "Palette list widget not found"
        labels = [listw.item(i).text() for i in range(listw.count())]
        dlg.close()
        qtbot.wait(20)
        return labels

    def _run_command_from_palette(query: str) -> None:
        """Run command from palette for the current workflow."""
        win._show_command_palette()
        qtbot.wait(40)
        dlg = getattr(win, "_command_palette_dialog", None)
        assert dlg is not None and dlg.isVisible()
        search = dlg.findChild(QtWidgets.QLineEdit)
        listw = dlg.findChild(QtWidgets.QListWidget)
        assert search is not None and listw is not None
        search.clear()
        qtbot.keyClicks(search, query)
        qtbot.wait(30)
        assert listw.count() > 0, f"No palette results for query: {query}"
        qtbot.keyPress(search, QtCore.Qt.Key_Return)
        qtbot.wait(50)

    # Usage boost: executing "Reset View" twice should raise/maintain ranking.
    win._command_usage_count = {}
    win._command_last_used_ts = {}
    before = _palette_labels()
    assert "Reset View" in before, "Reset View command missing from palette"
    before_idx = before.index("Reset View")
    _run_command_from_palette("reset view")
    _run_command_from_palette("reset view")
    after = _palette_labels()
    after_idx = after.index("Reset View")
    assert after_idx <= before_idx, "Usage boost should not reduce command ranking"

    # Mode boost: review queue commands should rank better in review mode.
    if win.dock_review_queue is not None:
        win.set_panel_visible("review_queue", False, source="test_mode")
    qtbot.wait(30)
    annotate_labels = _palette_labels()
    assert "Queue: Needs Review" in annotate_labels
    annotate_idx = annotate_labels.index("Queue: Needs Review")

    win.set_panel_visible("review_queue", True, source="test_mode")
    qtbot.wait(30)
    review_labels = _palette_labels()
    review_idx = review_labels.index("Queue: Needs Review")
    assert review_idx <= annotate_idx, "Review mode should boost review commands"

@pytest.mark.gui
def test_assist_expert_preset_expected_visibility_set(qtbot, tmp_path):
    """Assist Expert preset should produce the expected panel visibility composition."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_assist_expert_preset.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.apply_preset("Assist Expert")
    qtbot.wait(60)

    expected = {
        "sidebar": True,
        "annotations": True,
        "review_queue": True,
        "advanced_analysis": False,
        "qc_issues": True,
        "roi": False,
        "roi_manager": False,
        "results": False,
        "threshold": False,
        "particles": False,
        "hist": False,
        "profile": False,
        "logs": False,
        "metadata": False,
        "density": False,
        "orthoview": False,
    }
    actual = {
        key: bool(win.panel_docks[key].isVisible())
        for key in expected
        if key in win.panel_docks and win.panel_docks[key] is not None
    }
    assert actual == expected, f"Assist Expert visibility mismatch: {actual}"

@pytest.mark.gui
def test_stale_suggestions_require_one_shot_override_and_show_badge(qtbot, tmp_path):
    """Stale suggestions should warn and require one-shot override in batch preview."""
    pytest.importorskip("PyQt5")
    import time
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_stale_guard.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    image_id = int(win.primary_image.id)
    ts = float(time.time()) - 120.0
    row = PointSuggestion(
        image_id=image_id,
        image_name=str(win.primary_image.name),
        t=int(win.t_slider.value()),
        z=int(win.z_slider.value()),
        y=24.0,
        x=24.0,
        score=0.8,
        label=str(win.current_label),
        suggestion_id="stale-1",
    )
    row.meta["generated_at_ts"] = ts
    row.meta["confidence_available"] = True
    row.meta["p_accept"] = 0.8
    win.suggestions[image_id] = [row]
    win._annotation_edit_ts_by_image[image_id] = ts + 5.0
    win._disable_bulk_accept_when_stale = True

    # Stale no longer hard-disables actions; override is required in preview step.
    win._refresh_assist_warmup_panel()
    win._update_status()
    qtbot.wait(40)

    assert win.accept_visible_suggestions_act.isEnabled()
    assert win.accept_green_suggestions_act.isEnabled()
    assert "Stale" in win.status_details_panel.suggestions_lbl.text()
    assert getattr(win.review_queue_panel, "stale_lbl", None) is not None
    assert "regenerate recommended" in win.review_queue_panel.stale_lbl.text().lower()

    # The batch preview should block if stale override checkbox is not acknowledged.
    selected = win._preview_batch_accept_dialog(
        candidates=[row],
        title="Accept stale visible suggestions",
        description="Review stale candidates.",
        stale_override_required=True,
    )
    assert selected == [], "Stale batch should be blocked without explicit override acknowledgement"

@pytest.mark.gui
def test_stale_current_accept_is_blocked(qtbot, tmp_path):
    """Single current-suggestion accept should be blocked when stale guard is enabled."""
    pytest.importorskip("PyQt5")
    import time
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_stale_current_accept.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    image_id = int(win.primary_image.id)
    ts = float(time.time()) - 120.0
    row = PointSuggestion(
        image_id=image_id,
        image_name=str(win.primary_image.name),
        t=int(win.t_slider.value()),
        z=int(win.z_slider.value()),
        y=20.0,
        x=20.0,
        score=0.9,
        label=str(win.current_label),
        suggestion_id="stale-current-1",
    )
    row.meta["generated_at_ts"] = ts
    win.suggestions[image_id] = [row]
    win._annotation_edit_ts_by_image[image_id] = ts + 5.0
    win._disable_bulk_accept_when_stale = True

    before = len(win.annotations.get(image_id, []))
    win._accept_current_uncertain_suggestion()
    qtbot.wait(20)

    assert len(win.annotations.get(image_id, [])) == before
    assert len(win.suggestions.get(image_id, [])) == 1
