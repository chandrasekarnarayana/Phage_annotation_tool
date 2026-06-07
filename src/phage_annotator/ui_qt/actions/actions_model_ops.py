"""Extracted method group 11 for ActionsMixin."""

from __future__ import annotations

import gc
import json
import logging
import os
import pathlib
import time
from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets

from phage_annotator.analysis.core import compute_roi_mean_for_path, fit_bleach_curve
from phage_annotator.analysis.suggestion_rules import load_suggestion_rule_config
from phage_annotator.analysis.interactive_learning import InteractiveLearningModel
from phage_annotator.config import SUPPORTED_SUFFIXES
from phage_annotator.core.annotation import Keypoint, PointSuggestion
from phage_annotator.session.signal_hub import emit_annotations_changed
from phage_annotator.ui_qt.assist_state import assist_state_label
from phage_annotator.ui_qt.actions.assist_context import AssistContextMixin
from phage_annotator.ui_qt.actions import assist_generation, assist_review, assist_training
from phage_annotator.ui_qt.actions.assist_strategy import AssistStrategyMixin
from phage_annotator.ui_qt.actions.standard_workspace import WorkspaceActionsMixin
from phage_annotator.session.suggestion_commands import (
    AcceptSuggestionCommand,
    AcceptSuggestionsBatchCommand,
    ClearSuggestionsCommand,
    RejectSuggestionCommand,
)
from phage_annotator.ui_qt.actions.dock_actions import DockActionsMixin
from phage_annotator.ui_qt.actions.export_actions import ExportActionsMixin
from phage_annotator.ui_qt.actions.navigation_actions import NavigationActionsMixin
from phage_annotator.ui_qt.actions.qc_actions import QCActionsMixin
from phage_annotator.ui_qt.utils.debug import debug_log
from phage_annotator.ui_qt.utils.image_io import read_metadata
from phage_annotator.ui_qt.rendering.lut_manager import lut_names
from phage_annotator.io.metadata.reader import MetadataBundle


logger = logging.getLogger(__name__)



class ActionsModelOpsMixin:
    """Method group 11 extracted from ActionsMixin."""

    def _show_all_predictions_dialog(self) -> None:
        """Show a comprehensive dialog displaying all predictions/suggestions."""
        image_id = self.primary_image.id if self.primary_image else 0
        all_suggestions = self.suggestions.get(image_id, [])
        
        if not all_suggestions:
            QtWidgets.QMessageBox.information(
                self,
                "No Predictions",
                "No predictions/suggestions available. Please generate suggestions first using 'Suggest Points' from the Assist menu.",
            )
            return
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"All Predictions ({len(all_suggestions)} total)")
        dlg.resize(900, 600)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Info label
        info_label = QtWidgets.QLabel(
            f"Showing {len(all_suggestions)} predictions for current image. "
            f"Threshold: {self._suggestion_score_threshold:.2f}"
        )
        layout.addWidget(info_label)
        
        # Create table
        table = QtWidgets.QTableWidget(dlg)
        table.setColumnCount(10)
        table.setHorizontalHeaderLabels(
            ["ID", "Score", "X", "Y", "T", "Z", "Label", "ML Pred", "ML Conf", "Method"]
        )
        table.setRowCount(len(all_suggestions))
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Populate table
        for row_idx, suggestion in enumerate(all_suggestions):
            # ID (shortened)
            id_item = QtWidgets.QTableWidgetItem(str(suggestion.suggestion_id)[:12])
            id_item.setToolTip(str(suggestion.suggestion_id))
            table.setItem(row_idx, 0, id_item)
            
            # Score
            score_item = QtWidgets.QTableWidgetItem(f"{float(suggestion.score):.4f}")
            score = float(suggestion.score)
            # Color code by score
            if score >= 0.8:
                score_item.setBackground(QtGui.QColor(67, 160, 71, 100))  # Green
            elif score >= 0.5:
                score_item.setBackground(QtGui.QColor(253, 216, 53, 100))  # Yellow
            else:
                score_item.setBackground(QtGui.QColor(244, 67, 54, 100))  # Red
            table.setItem(row_idx, 1, score_item)
            
            # X, Y, T, Z
            table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(f"{float(suggestion.x):.2f}"))
            table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(f"{float(suggestion.y):.2f}"))
            table.setItem(row_idx, 4, QtWidgets.QTableWidgetItem(str(suggestion.t)))
            table.setItem(row_idx, 5, QtWidgets.QTableWidgetItem(str(suggestion.z)))
            
            # Label
            table.setItem(row_idx, 6, QtWidgets.QTableWidgetItem(str(suggestion.label)))
            
            # ML Prediction
            meta = dict(getattr(suggestion, "meta", {}) or {})
            ml_pred = meta.get("ml_prediction", None)
            ml_pred_text = "Accept" if ml_pred is True else "Reject" if ml_pred is False else "N/A"
            ml_pred_item = QtWidgets.QTableWidgetItem(ml_pred_text)
            if ml_pred is True:
                ml_pred_item.setBackground(QtGui.QColor(67, 160, 71, 100))  # Green
            elif ml_pred is False:
                ml_pred_item.setBackground(QtGui.QColor(244, 67, 54, 100))  # Red
            table.setItem(row_idx, 7, ml_pred_item)
            
            # ML Confidence
            ml_conf = meta.get("ml_confidence", None)
            ml_conf_text = f"{float(ml_conf):.3f}" if ml_conf is not None else "N/A"
            ml_conf_item = QtWidgets.QTableWidgetItem(ml_conf_text)
            if ml_conf is not None:
                conf_val = float(ml_conf)
                if conf_val >= 0.75:
                    ml_conf_item.setBackground(QtGui.QColor(67, 160, 71, 80))  # Green
                elif conf_val >= 0.5:
                    ml_conf_item.setBackground(QtGui.QColor(253, 216, 53, 80))  # Yellow
                else:
                    ml_conf_item.setBackground(QtGui.QColor(244, 67, 54, 80))  # Red
            table.setItem(row_idx, 8, ml_conf_item)
            
            # Method
            ml_method = meta.get("ml_method", "rule_based")
            method_text = "ML Trained" if ml_method == "ml_trained" else "Rule-based"
            table.setItem(row_idx, 9, QtWidgets.QTableWidgetItem(method_text))
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Statistics label
        high_score = sum(1 for s in all_suggestions if float(s.score) >= 0.8)
        medium_score = sum(1 for s in all_suggestions if 0.5 <= float(s.score) < 0.8)
        low_score = sum(1 for s in all_suggestions if float(s.score) < 0.5)
        
        ml_trained = sum(1 for s in all_suggestions if s.meta.get("ml_method") == "ml_trained")
        ml_accept = sum(1 for s in all_suggestions if s.meta.get("ml_prediction") is True)
        ml_reject = sum(1 for s in all_suggestions if s.meta.get("ml_prediction") is False)
        
        stats_label = QtWidgets.QLabel(
            f"Statistics: High score (≥0.8): {high_score} | "
            f"Medium score (0.5-0.8): {medium_score} | "
            f"Low score (<0.5): {low_score}<br>"
            f"ML Status: ML-trained: {ml_trained} | ML Accept: {ml_accept} | ML Reject: {ml_reject}"
        )
        layout.addWidget(stats_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        export_btn = QtWidgets.QPushButton("Export to CSV")
        close_btn = QtWidgets.QPushButton("Close")
        jump_btn = QtWidgets.QPushButton("Jump to Selected")
        
        button_layout.addWidget(export_btn)
        button_layout.addWidget(jump_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        # Connect buttons
        close_btn.clicked.connect(dlg.accept)
        
        def jump_to_selected():
            """Run the jump to selected workflow."""
            selected = table.selectedItems()
            if selected:
                row = table.currentRow()
                if 0 <= row < len(all_suggestions):
                    suggestion = all_suggestions[row]
                    self.t_slider.setValue(int(suggestion.t))
                    self.z_slider.setValue(int(suggestion.z))
                    self._request_ui_refresh("standard-actions")
                    dlg.accept()
        
        def export_to_csv():
            """Export to csv for the current workflow."""
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg, "Export Predictions to CSV", "", "CSV Files (*.csv)"
            )
            if path:
                import csv
                with open(path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Score", "X", "Y", "T", "Z", "Label", "Image"])
                    for s in all_suggestions:
                        writer.writerow([
                            s.suggestion_id,
                            float(s.score),
                            float(s.x),
                            float(s.y),
                            int(s.t),
                            int(s.z),
                            str(s.label),
                            str(s.image_name),
                        ])
                QtWidgets.QMessageBox.information(dlg, "Export Complete", f"Exported {len(all_suggestions)} predictions to:\n{path}")
        
        jump_btn.clicked.connect(jump_to_selected)
        export_btn.clicked.connect(export_to_csv)
        
        dlg.exec()
    def _on_suggestion_auto_retrain_changed(self, checked: bool) -> None:
        """Enable/disable periodic ranker retraining from labels."""
        assist_training.on_suggestion_auto_retrain_changed(self, checked)
    def _on_suggestion_min_labels_changed(self, value: int) -> None:
        """Set minimum labeled samples required before auto-retrain."""
        assist_training.on_suggestion_min_labels_changed(self, value)
    def _train_suggestion_ranker_now(self) -> None:
        """Force immediate ranker training from current labeled history."""
        assist_training.train_suggestion_ranker_now(self)
    def _show_calibration_visualizer(self) -> None:
        """Plot reliability-style p_accept calibration bins from reviewed suggestions."""
        assist_training.show_calibration_visualizer(self)
