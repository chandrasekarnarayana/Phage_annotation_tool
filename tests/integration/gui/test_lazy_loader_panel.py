"""Integration coverage for the lazy loader panel."""

from __future__ import annotations

import pytest


@pytest.mark.gui
def test_lazy_loader_folder_remove_and_ctrl_z_restore(qtbot, tmp_path):
    """Folder contents should be visible/selectable and removals should undo via Ctrl+Z."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtCore

    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    seed = generate_dummy_image(tmp_path / "seed.tif", mode="2d")
    folder = tmp_path / "batch"
    folder.mkdir()
    child_a = generate_dummy_image(folder / "child_a.tif", mode="2d")
    child_b = generate_dummy_image(folder / "child_b.tif", mode="2d")

    win = create_app([seed])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win._add_paths_to_lazy_loader([folder])
    qtbot.wait(80)

    tree = win.lazy_loader_tree
    assert tree.topLevelItemCount() >= 2
    folder_item = next(
        tree.topLevelItem(i)
        for i in range(tree.topLevelItemCount())
        if tree.topLevelItem(i).data(0, QtCore.Qt.ItemDataRole.UserRole) == str(folder)
    )
    assert folder_item.childCount() == 2

    tree.setCurrentItem(folder_item)
    assert tree.currentItem() is folder_item

    child_item = folder_item.child(0)
    child_path = str(child_item.data(0, QtCore.Qt.ItemDataRole.UserRole))
    tree.setCurrentItem(child_item)
    tree.setFocus()
    win._remove_selected_lazy_modality_view()
    qtbot.wait(80)
    assert not win._lazy_loader_manifest.contains(child_path)

    qtbot.keyClick(tree, QtCore.Qt.Key_Z, modifier=QtCore.Qt.KeyboardModifier.ControlModifier)
    qtbot.wait(80)
    assert win._lazy_loader_manifest.contains(child_path)
    assert str(child_a) in {str(img.path) for img in win._lazy_loader_source_images()}
    assert str(child_b) in {str(img.path) for img in win._lazy_loader_source_images()}


@pytest.mark.gui
def test_lazy_loader_table_has_no_default_projections_and_refreshes_canvas(qtbot, tmp_path):
    """The table should start without seeded mean/std rows and push changes to the canvas."""
    pytest.importorskip("PyQt5")

    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    first = generate_dummy_image(tmp_path / "first.tif", mode="2d")
    second = generate_dummy_image(tmp_path / "second.tif", mode="2d")

    win = create_app([first, second])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    qtbot.wait(120)

    names = [win.lazy_modality_table.item(row, 2).text() for row in range(win.lazy_modality_table.rowCount())]
    assert "Mean Projection" not in names
    assert "Std Projection" not in names

    refresh_calls = []
    win._refresh_image = lambda: refresh_calls.append("refresh")

    source_combo = win.lazy_modality_table.cellWidget(0, 3)
    assert source_combo.count() >= 2
    source_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: len(refresh_calls) > 0, timeout=1000)


@pytest.mark.gui
def test_lazy_loader_support_source_selector_uses_image_ids_not_combo_indices(qtbot, tmp_path):
    """Support-row source changes should map stable image ids back to the support image index."""
    pytest.importorskip("PyQt5")
    from PyQt5 import QtCore

    from phage_annotator.demo import generate_dummy_image
    from phage_annotator.ui_qt.main_window import create_app

    first = generate_dummy_image(tmp_path / "first.tif", mode="2d")
    second = generate_dummy_image(tmp_path / "second.tif", mode="2d")
    third = generate_dummy_image(tmp_path / "third.tif", mode="2d")

    win = create_app([first, second, third])
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    qtbot.wait(120)

    support_row = None
    for row in range(win.lazy_modality_table.rowCount()):
        item = win.lazy_modality_table.item(row, 2)
        if item is None:
            continue
        role = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if role == 1 or role == "builtin:support":
            support_row = row
            break

    assert support_row is not None

    refresh_calls = []
    win._refresh_image = lambda: refresh_calls.append("refresh")

    source_combo = win.lazy_modality_table.cellWidget(support_row, 3)
    target_image_id = int(source_combo.itemData(2))

    source_combo.setCurrentIndex(2)

    qtbot.waitUntil(lambda: len(refresh_calls) > 0, timeout=1000)
    assert win.support_image_idx == 2
    assert int(getattr(win.support_image, "id", -1)) == target_image_id
