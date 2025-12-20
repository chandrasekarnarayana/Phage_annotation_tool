import numpy as np
import pytest


@pytest.mark.gui
def test_gui_launch(qtbot, tmp_path) -> None:
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.gui_mpl import create_app

    path = generate_dummy_image(tmp_path / "dummy_gui.tif", mode="2d")
    win = create_app([path])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    assert win.isVisible()


@pytest.mark.gui
def test_gui_visual_regression(qtbot, tmp_path) -> None:
    pytest.importorskip("PyQt5")
    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.gui_mpl import create_app

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
