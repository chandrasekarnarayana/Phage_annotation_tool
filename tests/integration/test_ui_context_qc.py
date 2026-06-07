"""Integration tests for context actions and QC UI components."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

try:
    from PyQt5 import QtCore, QtWidgets

    _HAS_QT = True
except Exception:  # pragma: no cover - environment dependent
    QtCore = None  # type: ignore[assignment]
    QtWidgets = None  # type: ignore[assignment]
    _HAS_QT = False

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.core.annotation import Keypoint
from phage_annotator.session.qc_state import QCState

if _HAS_QT:
    from phage_annotator.session.context_commands import DeleteNearestCommand, MarkUncertainCommand
    from phage_annotator.ui_qt.panels.qc_issues_panel import QCIssuesPanel
    from phage_annotator.ui_qt.utils.context_menu import ContextMenuMixin
else:  # pragma: no cover - environment dependent
    DeleteNearestCommand = object  # type: ignore[assignment]
    MarkUncertainCommand = object  # type: ignore[assignment]
    QCIssuesPanel = object  # type: ignore[assignment]
    ContextMenuMixin = object  # type: ignore[assignment]


@pytest.fixture
def qapp():
    """Ensure a QApplication exists for Qt widgets."""
    if not _HAS_QT:
        pytest.skip("PyQt5 runtime unavailable for GUI integration tests.")
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


class _Slider:
    def __init__(self, value: int):
        """Initialize the object and prepare its runtime state."""
        self._value = value

    def value(self) -> int:
        """Run the value workflow."""
        return self._value


class _Action:
    def __init__(self) -> None:
        """Initialize the object and prepare its runtime state."""
        self.enabled = False

    def setEnabled(self, value: bool) -> None:
        """Run the setEnabled workflow."""
        self.enabled = bool(value)


class _FakeMenu:
    def __init__(self, selected_index: int) -> None:
        """Initialize the object and prepare its runtime state."""
        self._selected_index = selected_index
        self._actions: list[object] = []

    def addAction(self, _text: str) -> object:
        """Run the addAction workflow."""
        action = object()
        self._actions.append(action)
        return action

    def addSeparator(self) -> None:
        """Run the addSeparator workflow."""
        return None

    def exec(self, _global_pos):
        """Run the exec workflow."""
        return self._actions[self._selected_index]


class _WindowStub(ContextMenuMixin):
    def __init__(self, annotation_uncertain: bool = False) -> None:
        """Initialize the object and prepare its runtime state."""
        self.images = [object()]
        self.primary_image = Mock(id=0)
        self.annotations = {
            0: [
                Keypoint(
                    image_id=0,
                    image_name="img",
                    t=0,
                    z=0,
                    y=10.0,
                    x=12.0,
                    label="phage",
                    annotation_id="ann-1",
                    image_key="img",
                    source="manual",
                    meta={"uncertain": annotation_uncertain},
                    modality_idx=None,
                )
            ]
        }
        self.t_slider = _Slider(0)
        self.z_slider = _Slider(0)
        self.click_radius_px = 20.0
        self.controller = Mock()
        self.controller.execute_view_command.return_value = True
        self.controller.can_undo.return_value = True
        self.controller.can_redo.return_value = False
        self.undo_act = _Action()
        self.redo_act = _Action()
        self._refresh_table = Mock()
        self._refresh_image = Mock()
        self._update_status = Mock()
        self._mark_dirty = Mock()
        self._schedule_qc_validation = Mock()
        self._set_status = Mock()
        self._slice_data = Mock(return_value=None)


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_context_menu_delete_dispatches_view_command(monkeypatch, qapp):
    """Delete action should route through execute_view_command."""
    window = _WindowStub(annotation_uncertain=False)
    fake_menu = _FakeMenu(selected_index=0)  # Delete action

    monkeypatch.setattr(
        "phage_annotator.ui_qt.utils.context_menu.QtWidgets.QMenu",
        lambda _parent: fake_menu,
    )

    window._show_annotation_context_menu(12.0, 10.0, QtCore.QPoint(0, 0))

    window.controller.execute_view_command.assert_called_once()
    command = window.controller.execute_view_command.call_args[0][0]
    assert isinstance(command, DeleteNearestCommand)


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_context_menu_uncertain_dispatches_toggle_command(monkeypatch, qapp):
    """Uncertain action should route through MarkUncertainCommand."""
    window = _WindowStub(annotation_uncertain=False)
    fake_menu = _FakeMenu(selected_index=1)  # Uncertain action

    monkeypatch.setattr(
        "phage_annotator.ui_qt.utils.context_menu.QtWidgets.QMenu",
        lambda _parent: fake_menu,
    )

    window._show_annotation_context_menu(12.0, 10.0, QtCore.QPoint(0, 0))

    window.controller.execute_view_command.assert_called_once()
    command = window.controller.execute_view_command.call_args[0][0]
    assert isinstance(command, MarkUncertainCommand)
    assert command.uncertain is True


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_qc_panel_click_emits_jump_with_image_id(qapp):
    """Clicking an issue should emit jump coordinates plus image_id."""
    qc_state = QCState()
    issue = QCIssue(
        issue_id="dup-1",
        severity=IssueSeverity.ERROR,
        issue_type="duplicate",
        message="duplicate annotation",
        image_id=5,
        affected_annotation_ids=["a", "b"],
        location_x=100.0,
        location_y=200.0,
        location_z=3,
        location_t=7,
    )
    qc_state.add_issue(issue)
    panel = QCIssuesPanel(qc_state=qc_state)
    panel.refresh()

    observed = []
    panel.jump_to_location.connect(lambda x, y, z, t, image_id: observed.append((x, y, z, t, image_id)))

    assert panel.issue_widgets
    panel.issue_widgets[0].mousePressEvent(Mock())

    assert observed == [(100.0, 200.0, 3, 7, 5)]


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_qc_panel_export_buttons_emit_format(qapp):
    """Export buttons should emit requested report formats."""
    panel = QCIssuesPanel(qc_state=QCState())
    observed: list[str] = []
    panel.export_requested.connect(observed.append)

    panel.export_csv_btn.click()
    panel.export_json_btn.click()
    panel.export_html_btn.click()

    assert observed == ["csv", "json", "html"]


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_qc_panel_resolve_hides_issue_and_emits_status(qapp):
    """Resolve action should mark issue resolved and remove it from open list."""
    qc_state = QCState()
    issue = QCIssue(
        issue_id="dup-2",
        severity=IssueSeverity.ERROR,
        issue_type="duplicate",
        message="duplicate annotation",
        image_id=1,
        affected_annotation_ids=["a", "b"],
        location_x=10.0,
        location_y=20.0,
        location_z=0,
        location_t=0,
    )
    qc_state.add_issue(issue)
    panel = QCIssuesPanel(qc_state=qc_state)
    panel.refresh()

    observed: list[tuple[str, str]] = []
    panel.issue_status_changed.connect(lambda issue_id, status: observed.append((issue_id, status)))

    resolve_buttons = [
        btn
        for btn in panel.findChildren(QtWidgets.QPushButton)
        if btn.text() == "Resolve"
    ]
    assert resolve_buttons
    resolve_buttons[0].click()

    assert qc_state.get_issue_status("dup-2") == qc_state.STATUS_RESOLVED
    assert panel.get_visible_issue_count() == 0
    assert observed == [("dup-2", qc_state.STATUS_RESOLVED)]


@pytest.mark.gui
@pytest.mark.skipif(not _HAS_QT, reason="PyQt5 runtime unavailable")
def test_qc_panel_show_resolved_filter_restores_visibility(qapp):
    """Resolved issues are hidden by default and shown when filter is enabled."""
    qc_state = QCState()
    issue = QCIssue(
        issue_id="dup-3",
        severity=IssueSeverity.ERROR,
        issue_type="duplicate",
        message="duplicate annotation",
        image_id=1,
        affected_annotation_ids=["a", "b"],
        location_x=11.0,
        location_y=21.0,
        location_z=0,
        location_t=0,
    )
    qc_state.add_issue(issue)
    panel = QCIssuesPanel(qc_state=qc_state)
    panel.refresh()

    # Resolve issue via state and refresh panel.
    assert qc_state.resolve_issue("dup-3") is True
    panel.refresh()
    assert panel.get_visible_issue_count() == 0

    # Enable "Show Resolved" and verify issue becomes visible again.
    panel.show_resolved_checkbox.setChecked(True)
    assert panel.get_visible_issue_count() == 1
