"""Basic Qt application launch smoke tests."""

import numpy as np
import pytest


@pytest.mark.gui
# Widget initialization issues resolved by adding all missing widgets.
# to the active UI setup helpers. GUI now launches successfully. Re-enabling test.
def test_gui_launch(qtbot, tmp_path) -> None:
    """Verify gui launch for the current workflow."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "dummy_gui.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    assert win.isVisible()


@pytest.mark.gui
# Widget initialization issues resolved. Re-enabling test.
def test_gui_visual_regression(qtbot, tmp_path) -> None:
    """Verify gui visual regression for the current workflow."""
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    path = generate_dummy_image(tmp_path / "dummy_gui_vis.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.canvas.draw()
    img1 = np.asarray(win.canvas.buffer_rgba(), dtype=np.int16)

    # Trigger a redraw; expect stable rendering when data/controls unchanged.
    win._refresh_image()
    win.canvas.draw()
    img2 = np.asarray(win.canvas.buffer_rgba(), dtype=np.int16)

    diff = np.abs(img1 - img2).mean()
    assert diff < 1.0  # tolerate minor float/render jitter
