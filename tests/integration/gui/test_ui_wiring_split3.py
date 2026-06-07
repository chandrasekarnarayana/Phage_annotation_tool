"""Split definitions from test_ui_wiring.py."""


import pytest


@pytest.mark.gui
def test_stale_review_accept_is_blocked(qtbot, tmp_path):
    """Review-panel accept should be blocked when the selected suggestion is stale."""
    pytest.importorskip("PyQt5")
    import time
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_stale_review_accept.tif", mode="2d")
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
        y=22.0,
        x=22.0,
        score=0.9,
        label=str(win.current_label),
        suggestion_id="stale-review-1",
    )
    row.meta["generated_at_ts"] = ts
    win.suggestions[image_id] = [row]
    win._annotation_edit_ts_by_image[image_id] = ts + 5.0
    win._disable_bulk_accept_when_stale = True

    before = len(win.annotations.get(image_id, []))
    win._set_selected_suggestion_decision(row.suggestion_id, "accepted")
    qtbot.wait(20)

    assert len(win.annotations.get(image_id, [])) == before
    assert len(win.suggestions.get(image_id, [])) == 1

@pytest.mark.gui
def test_stale_roi_accept_is_blocked_and_reports_count(qtbot, tmp_path):
    """ROI accept should block stale suggestions and report the blocked count."""
    pytest.importorskip("PyQt5")
    import time
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_stale_roi_accept.tif", mode="2d")
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
        score=0.9,
        label=str(win.current_label),
        suggestion_id="stale-roi-1",
    )
    row.meta["generated_at_ts"] = ts
    win.suggestions[image_id] = [row]
    win._annotation_edit_ts_by_image[image_id] = ts + 5.0
    win._disable_bulk_accept_when_stale = True
    win.roi_shape = "box"
    win.roi_rect = (10.0, 10.0, 30.0, 30.0)

    before = len(win.annotations.get(image_id, []))
    win._accept_suggestions_in_roi()
    qtbot.wait(20)

    assert len(win.annotations.get(image_id, [])) == before
    assert len(win.suggestions.get(image_id, [])) == 1
    assert "blocked" in win.statusBar().currentMessage().lower()

@pytest.mark.gui
def test_interactive_learning_flag_controls_metadata_path(qtbot, tmp_path):
    """Experimental sidecar metadata should appear only while the feature flag is enabled."""
    pytest.importorskip("PyQt5")
    from phage_annotator.core.annotation import PointSuggestion
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_interactive_learning_flag.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    suggestion = PointSuggestion(
        image_id=int(win.primary_image.id),
        image_name=str(win.primary_image.name),
        t=0,
        z=0,
        y=12.0,
        x=12.0,
        score=0.7,
        label=str(win.current_label),
        suggestion_id="ml-flag-1",
    )
    suggestion.meta["ml_prediction"] = True
    suggestion.meta["ml_confidence"] = 0.95
    ranked = win._rank_and_calibrate_suggestions([suggestion])
    assert ranked[0].meta.get("ml_prediction") is None

    win._on_interactive_learning_experimental_changed(True)
    assert win.controller.feature_enabled("interactive_learning_experimental", False) is True
    assert hasattr(win, "_interactive_learning_model")
    win._interactive_learning_model.is_trained = True
    win._interactive_learning_model.predict = lambda rows: [
        {
            "accepted": True,
            "confidence": 0.88,
            "uncertainty": 0.12,
            "method": "interactive",
        }
        for _ in rows
    ]
    enabled_row = PointSuggestion(
        image_id=int(win.primary_image.id),
        image_name=str(win.primary_image.name),
        t=0,
        z=0,
        y=14.0,
        x=14.0,
        score=0.65,
        label=str(win.current_label),
        suggestion_id="ml-flag-2",
    )
    enabled_ranked = win._rank_and_calibrate_suggestions([enabled_row])
    assert enabled_ranked[0].meta.get("ml_prediction") is True
    assert enabled_ranked[0].meta.get("ml_confidence") == 0.88

    win._on_interactive_learning_experimental_changed(False)
    assert win.controller.feature_enabled("interactive_learning_experimental", False) is False
    disabled_row = PointSuggestion(
        image_id=int(win.primary_image.id),
        image_name=str(win.primary_image.name),
        t=0,
        z=0,
        y=16.0,
        x=16.0,
        score=0.62,
        label=str(win.current_label),
        suggestion_id="ml-flag-3",
    )
    disabled_row.meta["ml_prediction"] = True
    disabled_row.meta["ml_confidence"] = 0.99
    disabled_ranked = win._rank_and_calibrate_suggestions([disabled_row])
    assert disabled_ranked[0].meta.get("ml_prediction") is None
    assert disabled_ranked[0].meta.get("ml_confidence") is None

@pytest.mark.gui
def test_effective_assist_context_line_mirrors_status_and_queue(qtbot, tmp_path):
    """Effective Assist Context must be visible and synchronized in status + review queue."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_effective_context_sync.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._suggestion_strategy = "current_view"
    win._active_evidence_preset_name = "default"
    win.annotate_target = "frame"
    win.annotation_scope = "current"
    win._refresh_assist_warmup_panel()
    win._update_status()
    qtbot.wait(40)

    status_txt = win.status_details_panel.context_lbl.text()
    queue_txt = win.review_queue_panel.context_lbl.text()
    assert "Strategy=" in status_txt and "Preset=" in status_txt
    assert queue_txt.startswith("Effective Assist Context: ")
    assert f"Effective Assist Context: {status_txt}" == queue_txt

@pytest.mark.gui
def test_modality_ab_compare_preserves_camera_limits(qtbot, tmp_path):
    """A/B layer preset compare should preserve frame-axis camera limits."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_ab_compare_camera.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._evidence_layer_presets = {
        "A": {"current_view": {"visible": True, "opacity": 1.0, "lut": "gray", "role": "view"}},
        "B": {"current_view": {"visible": True, "opacity": 0.5, "lut": "magma", "role": "proposal"}},
    }
    frame_ax = win.renderer.get_axis("frame")
    assert frame_ax is not None
    frame_ax.set_xlim(20.0, 70.0)
    frame_ax.set_ylim(80.0, 10.0)
    before = (tuple(frame_ax.get_xlim()), tuple(frame_ax.get_ylim()))

    win._compare_modality_layer_presets("A", "B")
    qtbot.wait(40)
    after = (tuple(frame_ax.get_xlim()), tuple(frame_ax.get_ylim()))
    assert after == before, f"Camera limits should stay unchanged during compare: {before} -> {after}"

@pytest.mark.gui
def test_status_modality_combo_switches_active_view(qtbot, tmp_path):
    """Status-bar modality selector should switch the active view."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    p0 = generate_dummy_image(tmp_path / "test_modality_status_0.tif", mode="2d")
    p1 = generate_dummy_image(tmp_path / "test_modality_status_1.tif", mode="2d")
    win = create_app([p0, p1])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    assert win.status_modality_combo.count() >= 2

    initial = int(win.current_image_idx)
    target = 1 if initial == 0 else 0
    win.status_modality_combo.setCurrentIndex(target)
    qtbot.wait(60)

    assert int(win.current_image_idx) == target
    assert int(win.status_modality_combo.currentIndex()) == target

@pytest.mark.gui
def test_review_context_pack_shows_review_panels(qtbot, tmp_path):
    """Review context pack should surface review queue and embedded rationale panel."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "test_review_pack_layers.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Collapse then enable pack.
    win.set_panel_visible("review_queue", False, source="test")
    qtbot.wait(20)

    win._toggle_review_context_pack()
    qtbot.wait(40)
    assert win.panel_docks["review_queue"].isVisible()
    assert getattr(win, "review_queue_panel", None) is not None
    assert getattr(win.review_queue_panel, "explain_panel", None) is not None
    assert win.review_queue_panel.explain_panel.isVisible()
