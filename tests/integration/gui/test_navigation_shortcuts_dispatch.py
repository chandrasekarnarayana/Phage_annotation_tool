"""GUI integration tests for jump-to-frame and jump-to-z shortcut dispatch."""

from __future__ import annotations

import pytest


@pytest.mark.gui
def test_jump_to_frame_shortcut_dispatch_and_history(tmp_path, monkeypatch):
    """Ctrl+G should dispatch to frame dialog and integrate with undo/redo."""
    pytest.importorskip("PyQt5")
    pytest.importorskip("PyQt5.sip")
    from PyQt5 import QtCore, QtTest, QtWidgets

    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app
    from phage_annotator.ui_qt.actions import standard as standard_actions

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = generate_dummy_image(tmp_path / "test_jump_frame_dispatch.tif", mode="tz")
    win = create_app([path])
    win.show()
    QtTest.QTest.qWaitForWindowExposed(win)
    win.raise_()
    win.activateWindow()
    win.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)
    QtTest.QTest.qWait(50)

    assert win.t_slider.value() == 0

    calls = {"count": 0}

    def _fake_get_int(*args, **kwargs):
        calls["count"] += 1
        return 2, True  # 1-based index -> target frame index 1

    monkeypatch.setattr(standard_actions.QtWidgets.QInputDialog, "getInt", _fake_get_int)

    QtTest.QTest.keyClick(win, QtCore.Qt.Key_G, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtTest.QTest.qWait(80)
    assert calls["count"] == 1
    assert win.t_slider.value() == 1
    assert win.undo_act.isEnabled()

    QtTest.QTest.keyClick(win, QtCore.Qt.Key_Z, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtTest.QTest.qWait(80)
    assert win.t_slider.value() == 0

    QtTest.QTest.keyClick(
        win,
        QtCore.Qt.Key_Z,
        QtCore.Qt.KeyboardModifier.ControlModifier
        | QtCore.Qt.KeyboardModifier.ShiftModifier,
    )
    QtTest.QTest.qWait(80)
    assert win.t_slider.value() == 1
    win.close()
    app.processEvents()


@pytest.mark.gui
def test_jump_to_z_shortcut_dispatch_and_history(tmp_path, monkeypatch):
    """Ctrl+Shift+G should dispatch to z dialog and integrate with undo/redo."""
    pytest.importorskip("PyQt5")
    pytest.importorskip("PyQt5.sip")
    from PyQt5 import QtCore, QtTest, QtWidgets

    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app
    from phage_annotator.ui_qt.actions import standard as standard_actions

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    path = generate_dummy_image(tmp_path / "test_jump_z_dispatch.tif", mode="tz")
    win = create_app([path])
    win.show()
    QtTest.QTest.qWaitForWindowExposed(win)
    win.raise_()
    win.activateWindow()
    win.setFocus(QtCore.Qt.FocusReason.ActiveWindowFocusReason)
    QtTest.QTest.qWait(50)

    assert win.z_slider.value() == 0

    calls = {"count": 0}

    def _fake_get_int(*args, **kwargs):
        calls["count"] += 1
        return 3, True  # 1-based index -> target z index 2

    monkeypatch.setattr(standard_actions.QtWidgets.QInputDialog, "getInt", _fake_get_int)

    QtTest.QTest.keyClick(
        win,
        QtCore.Qt.Key_G,
        QtCore.Qt.KeyboardModifier.ControlModifier
        | QtCore.Qt.KeyboardModifier.ShiftModifier,
    )
    QtTest.QTest.qWait(80)
    assert calls["count"] == 1
    assert win.z_slider.value() == 2
    assert win.undo_act.isEnabled()

    QtTest.QTest.keyClick(win, QtCore.Qt.Key_Z, QtCore.Qt.KeyboardModifier.ControlModifier)
    QtTest.QTest.qWait(80)
    assert win.z_slider.value() == 0

    QtTest.QTest.keyClick(
        win,
        QtCore.Qt.Key_Z,
        QtCore.Qt.KeyboardModifier.ControlModifier
        | QtCore.Qt.KeyboardModifier.ShiftModifier,
    )
    QtTest.QTest.qWait(80)
    assert win.z_slider.value() == 2
    win.close()
    app.processEvents()
