"""Extracted method group 3 for SmlmDockWidget."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from phage_annotator.smlm.backends import discover_bundled_thunderstorm_jar
from phage_annotator.smlm.external_plugins import discover_external_fiji_plugins




class ContextMenuMixin:
    """Method group 3 extracted from SmlmDockWidget."""

    def export_localizations_csv(self, path: str) -> None:
        """Export localizations csv for the current workflow."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "frame_index",
                    "x_px",
                    "y_px",
                    "sigma_px",
                    "photons",
                    "background",
                    "uncertainty_px",
                    "label",
                ]
            )
            for loc in self._localizations:
                writer.writerow(
                    [
                        int(getattr(loc, "frame_index", 0)),
                        f"{float(getattr(loc, 'x_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'y_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'sigma_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'photons', 0.0)):.4f}",
                        f"{float(getattr(loc, 'background', 0.0)):.4f}",
                        f"{float(getattr(loc, 'uncertainty_px', 0.0)):.4f}",
                        str(getattr(loc, "label", "") or ""),
                    ]
                )
    def _update_selection_state(self) -> None:
        """Update selection state for the current workflow."""
        total = len(self._localizations)
        selected = len(self.selected_localization_indices())
        if total == 0:
            self.add_ann_btn.setEnabled(False)
            self.add_ann_btn.setText("Add to Annotations")
            return
        if selected > 0:
            self.results_summary_lbl.setText(f"{total} localizations available | {selected} selected")
            self.add_ann_btn.setEnabled(True)
            self.add_ann_btn.setText(f"Add Selected ({selected})")
        else:
            self.results_summary_lbl.setText(f"{total} localizations available.")
            self.add_ann_btn.setEnabled(True)
            self.add_ann_btn.setText(f"Add All ({total})")
    def _copy_selected_results(self) -> None:
        """Copy selected results for the current workflow."""
        indices = self.selected_localization_indices()
        if not indices:
            return
        lines = ["frame_index\tx_px\ty_px\tsigma_px\tphotons\tuncertainty_px"]
        for row in indices:
            loc = self._localizations[row]
            lines.append(
                "\t".join(
                    [
                        str(int(getattr(loc, "frame_index", 0))),
                        f"{float(getattr(loc, 'x_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'y_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'sigma_px', 0.0)):.4f}",
                        f"{float(getattr(loc, 'photons', 0.0)):.4f}",
                        f"{float(getattr(loc, 'uncertainty_px', 0.0)):.4f}",
                    ]
                )
            )
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
    def _open_results_context_menu(self, pos: QtCore.QPoint) -> None:
        """Open results context menu for the current workflow."""
        menu = QtWidgets.QMenu(self)
        copy_act = menu.addAction("Copy Selected")
        select_all_act = menu.addAction("Select All")
        clear_sel_act = menu.addAction("Clear Selection")
        chosen = menu.exec_(self.results_table.viewport().mapToGlobal(pos))
        if chosen is copy_act:
            self._copy_selected_results()
        elif chosen is select_all_act:
            self.results_table.selectAll()
        elif chosen is clear_sel_act:
            self.results_table.clearSelection()
    def set_generated_macro(self, macro_text: str) -> None:
        """Set generated/executed macro text in debug panel."""
        self.generated_macro_view.setPlainText((macro_text or "").strip())
    def clear_fixit_card(self) -> None:
        """Hide and clear guided fix card."""
        self._clear_fixit_buttons()
        self.fixit_title_label.setText("")
        self.fixit_detail_label.setText("")
        self.fixit_group.setVisible(False)
    def set_fixit_card(
        self,
        *,
        title: str,
        detail: str,
        actions: list[tuple[str, Callable[[], None]]],
    ) -> None:
        """Show guided fix card with actionable buttons."""
        self._clear_fixit_buttons()
        self.fixit_title_label.setText(title.strip())
        self.fixit_detail_label.setText(detail.strip())
        for label, handler in actions:
            btn = QtWidgets.QPushButton(label)
            btn.clicked.connect(handler)
            self.fixit_actions_layout.addWidget(btn)
        self.fixit_actions_layout.addStretch(1)
        self.fixit_group.setVisible(True)
    def _clear_fixit_buttons(self) -> None:
        """Clear fixit buttons for the current workflow."""
        while self.fixit_actions_layout.count():
            item = self.fixit_actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
