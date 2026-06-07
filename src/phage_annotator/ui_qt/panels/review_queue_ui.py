"""Extracted method group 2 for ReviewQueuePanel."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.ui_qt.panels.suggestion_explain_panel import SuggestionExplainPanel
from phage_annotator.ui_qt.services.panel_logging import get_panel_logger



class ReviewQueueUiMixin:
    """Method group 2 extracted from ReviewQueuePanel."""

    def _show_keyboard_shortcuts(self) -> None:
        """Show a helpful dialog with keyboard shortcuts for assist workflow."""
        shortcuts = [
            ("A", "Accept current suggestion"),
            ("R", "Reject current suggestion"),
            ("N", "Skip to next suggestion"),
            ("W", "Jump to next uncertain"),
            ("A → N", "Accept & move to next (fast workflow)"),
            ("Space", "Pan view to suggestion"),
        ]
        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("Assist Keyboard Shortcuts")
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        
        text = "Quick Keyboard Reference:\n\n"
        for key, desc in shortcuts:
            text += f"  {key:<8} → {desc}\n"
        text += "\n💡 Tip: Hover over buttons for more details"
        
        msg_box.setText(text)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.exec()
    def _toggle_advanced_controls(self, checked: bool) -> None:
        """Show or hide advanced assist controls."""
        self.advanced_container.setVisible(bool(checked))
        self.advanced_toggle_btn.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if bool(checked) else QtCore.Qt.ArrowType.RightArrow
        )
    def set_suggestions(self, rows: list[dict[str, str]], current_row: int) -> None:
        """Populate suggested-points table and keep selected row in sync."""
        logger = get_panel_logger("assist")
        status_bg = {
            "accepted": QtGui.QColor("#e8f5e9"),
            "rejected": QtGui.QColor("#ffebee"),
            "proposed": QtGui.QColor("#fffde7"),
        }
        status_fg = {
            "accepted": QtGui.QColor("#1b5e20"),
            "rejected": QtGui.QColor("#b71c1c"),
            "proposed": QtGui.QColor("#7f6000"),
        }
        
        # Log suggestion queue update
        accepted = sum(1 for r in rows if str(r.get("status", "")).lower() == "accepted")
        rejected = sum(1 for r in rows if str(r.get("status", "")).lower() == "rejected")
        proposed = len(rows) - accepted - rejected
        logger.log_action(
            "suggestion_queue_updated",
            total_suggestions=len(rows),
            accepted_count=accepted,
            rejected_count=rejected,
            proposed_count=proposed,
            current_row_idx=current_row,
        )
        
        self.suggestions_table.blockSignals(True)
        self.suggestions_table.setRowCount(len(rows))
        for ridx, row in enumerate(rows):
            key = str(row.get("status", "proposed")).strip().lower()
            t_val = str(row.get("t", "-"))
            z_val = str(row.get("z", "-"))
            t_z = f"{t_val}/{z_val}" if t_val != "-" or z_val != "-" else "-"
            action_state = str(row.get("state", "proposed")).upper()
            if key == "accepted":
                action_state = "✓ ACCEPT"
            elif key == "rejected":
                action_state = "✗ REJECT"
            values = [
                str(row.get("index", ridx + 1)),
                str(row.get("x", "-")),
                str(row.get("y", "-")),
                t_z,
                str(row.get("acceptance", "n/a")),
                action_state,
            ]
            for cidx, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                if cidx == 0:
                    item.setData(QtCore.Qt.ItemDataRole.UserRole, str(row.get("suggestion_id", "")))
                if key in status_bg:
                    item.setBackground(status_bg[key])
                if cidx == 4 and key in status_fg:
                    item.setForeground(status_fg[key])
                if cidx == 5 and key in status_fg:
                    item.setForeground(status_fg[key])
                self.suggestions_table.setItem(ridx, cidx, item)
        if rows:
            row = max(0, min(int(current_row), len(rows) - 1))
            self.suggestions_table.selectRow(row)
            self.suggestions_table.scrollToItem(
                self.suggestions_table.item(row, 0),
                QtWidgets.QAbstractItemView.ScrollHint.PositionAtCenter,
            )
        self.suggestions_table.blockSignals(False)
    def _emit_selected_suggestion_row(self) -> None:
        """Emit selected row for controller-driven focus actions."""
        indexes = self.suggestions_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = int(indexes[0].row())
        self.suggestion_row_selected.emit(row)
    def _selected_suggestion_id(self) -> str:
        """Return selected suggestion id from table row metadata."""
        indexes = self.suggestions_table.selectionModel().selectedRows()
        if not indexes:
            return ""
        row = int(indexes[0].row())
        item = self.suggestions_table.item(row, 0)
        if item is None:
            return ""
        return str(item.data(QtCore.Qt.ItemDataRole.UserRole) or "")
    def _emit_decision_for_selected(self, status: str) -> None:
        """Emit desired decision for the currently selected suggestion row."""
        suggestion_id = self._selected_suggestion_id()
        if not suggestion_id:
            return
        self.decision_requested.emit(suggestion_id, str(status))
