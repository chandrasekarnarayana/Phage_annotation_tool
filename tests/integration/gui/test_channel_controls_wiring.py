"""GUI integration tests for channel controls wiring."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import tifffile as tif


def _write_multichannel_stack(path: Path, channels: int = 3) -> Path:
    """Create a small CTZYX test stack with deterministic channel contrast."""
    rng = np.random.default_rng(123)
    data = np.zeros((channels, 4, 2, 48, 48), dtype=np.uint16)  # C, T, Z, Y, X
    for channel_idx in range(channels):
        base = (channel_idx + 1) * 1000
        noise = rng.integers(0, 250, size=(4, 2, 48, 48), dtype=np.uint16)
        data[channel_idx] = base + noise
    tif.imwrite(path, data, metadata={"axes": "CTZYX"}, photometric="minisblack")
    return path


@pytest.mark.gui
def test_channel_panel_updates_session_settings(qtbot, tmp_path):
    """Channel panel interactions should persist to session state and drive RGB frame render."""
    pytest.importorskip("PyQt5")
    from phage_annotator.ui_qt.main_window import create_app

    multi_path = _write_multichannel_stack(tmp_path / "multi_ctzyx.tif")
    win = create_app([multi_path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    qtbot.wait(120)

    assert win.channel_panel is not None
    assert win.dock_channels is not None
    assert win.primary_image.channel_count == 3
    assert isinstance(win.controller.session_state.channel_display_settings, dict)
    assert win.controller.session_state.channel_display_settings["channel_count"] == 3

    # Toggle visibility of channel 1.
    ch1_visible = win.channel_panel._channel_widgets[1]["visibility"]
    ch1_visible.setChecked(False)
    qtbot.wait(50)
    settings = win.controller.session_state.channel_display_settings
    assert settings["channels"][1]["visible"] is False

    # Adjust opacity for channel 2.
    ch2_opacity = win.channel_panel._channel_widgets[2]["opacity_slider"]
    ch2_opacity.setValue(35)
    qtbot.wait(50)
    settings = win.controller.session_state.channel_display_settings
    assert settings["channels"][2]["opacity"] == pytest.approx(0.35, rel=1e-2)

    # Switch blend mode.
    blend_idx = win.channel_panel.blend_combo.findData("screen")
    assert blend_idx >= 0
    win.channel_panel.blend_combo.setCurrentIndex(blend_idx)
    qtbot.wait(50)
    settings = win.controller.session_state.channel_display_settings
    assert settings["blend_mode"] == "screen"

    # Multi-channel render path should produce an RGB frame.
    win._refresh_image()
    frame_data = np.asarray(win.im_frame.get_array())
    assert frame_data.ndim == 3
    assert frame_data.shape[2] == 3

    export_frame = win._export_panel_frame(
        win.primary_image,
        win.support_image,
        t_idx=win.t_slider.value(),
        z_idx=win.z_slider.value(),
        panel="frame",
        crop_rect=None,
    )
    assert export_frame is not None
    assert export_frame.ndim == 3
    assert export_frame.shape[2] == 3


@pytest.mark.gui
def test_channel_panel_visibility_tracks_active_image(qtbot, tmp_path):
    """Channels dock should hide on single-channel images and return for multi-channel ones."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    multi_path = _write_multichannel_stack(tmp_path / "multi_switch.tif")
    single_path = generate_dummy_image(tmp_path / "single_tzyx.tif", mode="tz")
    win = create_app([multi_path, single_path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    qtbot.wait(120)

    assert win.primary_image.channel_count > 1
    assert win.dock_channels is not None
    assert win.dock_channels.isVisible()

    win._set_fov(1)  # single-channel image
    qtbot.wait(120)
    assert win.primary_image.channel_count == 1
    assert not win.dock_channels.isVisible()

    win._set_fov(0)  # back to multi-channel image
    qtbot.wait(120)
    assert win.primary_image.channel_count > 1
    assert win.dock_channels.isVisible()
