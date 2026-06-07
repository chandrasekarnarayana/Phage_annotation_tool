"""Extracted method group 12 for ActionsMixin."""

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



class ActionsModelPersistenceMixin:
    """Method group 12 extracted from ActionsMixin."""

    def _show_interactive_learning_stats(self) -> None:
        """Show statistics and status of the interactive learning model (Weka-inspired)."""
        if not self._interactive_learning_enabled():
            QtWidgets.QMessageBox.information(
                self,
                "Interactive Learning",
                "Interactive learning is disabled. Enable the experimental sidecar in Assist settings first.",
            )
            return
        
        model = self._interactive_learning_model
        stats = model.get_statistics()
        
        # Create dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Interactive Learning Model Statistics")
        dlg.resize(600, 400)
        layout = QtWidgets.QVBoxLayout(dlg)
        
        # Model info
        info_text = f"""<b>Interactive Learning Model (Weka-inspired)</b><br><br>
        <b>Status:</b> {"✅ Trained" if model.is_trained else "⏳ Not trained yet"}<br>
        <b>Model Type:</b> {model.model_type}<br>
        <b>Training Examples:</b> {stats['n_examples']}<br>
        <b>Accepts:</b> {stats['n_accepts']} | <b>Rejects:</b> {stats['n_rejects']}<br>
        <b>Model Version:</b> {stats['version']}<br>
        <b>Update Frequency:</b> Every {model.update_frequency} examples<br>
        <b>Min Examples to Train:</b> {model.min_examples_to_train}<br><br>
        """
        
        if model.is_trained:
            info_text += f"<b>Training Accuracy:</b> {stats.get('training_accuracy', 0.0):.2%}<br>"
        
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Feature importance (if trained)
        if model.is_trained:
            importance = model.get_feature_importance()
            if importance:
                layout.addWidget(QtWidgets.QLabel("<b>Top 10 Important Features:</b>"))
                
                importance_table = QtWidgets.QTableWidget()
                importance_table.setColumnCount(2)
                importance_table.setHorizontalHeaderLabels(["Feature", "Importance"])
                importance_table.setRowCount(min(10, len(importance)))
                
                sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
                for i, (feature, imp) in enumerate(sorted_importance[:10]):
                    importance_table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(feature)))
                    importance_table.setItem(i, 1, QtWidgets.QTableWidgetItem(f"{float(imp):.4f}"))
                
                importance_table.resizeColumnsToContents()
                layout.addWidget(importance_table)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        if not model.is_trained and stats['n_examples'] >= model.min_examples_to_train:
            train_btn = QtWidgets.QPushButton("🎓 Train Now")
            def train_now():
                """Train now for the current workflow."""
                model.train()
                self._status_success(
                    f"Interactive learning model trained with {stats['n_examples']} examples.",
                    timeout_ms=3500,
                    source="standard.interactive_learning",
                )
                dlg.accept()
                self._show_interactive_learning_stats()  # Reopen with updated stats
            train_btn.clicked.connect(train_now)
            button_layout.addWidget(train_btn)
        
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dlg.exec()
    def _save_interactive_learning_model(self) -> None:
        """Save the interactive learning model to a file."""
        if not self._interactive_learning_enabled():
            return
        
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Interactive Learning Model",
            "",
            "Model Files (*.pkl);;All Files (*)",
        )
        
        if not path:
            return
        
        try:
            self._interactive_learning_model.save(path)
            self._status_success(
                f"Interactive learning model saved to {path}.",
                timeout_ms=3500,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Saved",
                f"Interactive learning model saved successfully to:\n{path}",
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Save Failed",
                f"Failed to save model:\n{str(e)}",
            )
    def _load_interactive_learning_model(self) -> None:
        """Load an interactive learning model from a file."""
        if not self._interactive_learning_enabled():
            return
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Load Interactive Learning Model",
            "",
            "Model Files (*.pkl);;All Files (*)",
        )
        
        if not path:
            return
        
        try:
            loaded_model = InteractiveLearningModel.load(path)
            self._interactive_learning_model = loaded_model
            stats = loaded_model.get_statistics()
            self._status_success(
                f"Interactive learning model loaded: {stats['n_examples']} examples, "
                f"{'trained' if loaded_model.is_trained else 'not trained'}.",
                timeout_ms=3500,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Loaded",
                f"Interactive learning model loaded successfully from:\n{path}\n\n"
                f"Training examples: {stats['n_examples']}\n"
                f"Status: {'Trained' if loaded_model.is_trained else 'Not trained'}",
            )
            # Refresh predictions with new model
            if self.primary_image is not None:
                self._request_ui_refresh("standard-actions")
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Load Failed",
                f"Failed to load model:\n{str(e)}",
            )
    def _reset_interactive_learning_model(self) -> None:
        """Reset the interactive learning model (clear all training examples)."""
        if not self.controller.feature_enabled("interactive_learning_experimental", False):
            return

        if not hasattr(self, "_interactive_learning_model"):
            self._interactive_learning_model = InteractiveLearningModel()
            self._status_info(
                "Interactive learning model initialized.",
                timeout_ms=3000,
                source="standard.interactive_learning",
            )
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Reset Interactive Learning Model",
            "This will clear all training examples and reset the model.\n"
            "This action cannot be undone.\n\n"
            "Are you sure you want to continue?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        
        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Create a new model with same config
            old_model = self._interactive_learning_model
            self._interactive_learning_model = InteractiveLearningModel(
                model_type=old_model.model_type,
                update_frequency=old_model.update_frequency,
                min_examples_to_train=old_model.min_examples_to_train,
                confidence_threshold=old_model.confidence_threshold,
            )
            self._status_info(
                "Interactive learning model reset.",
                timeout_ms=3000,
                source="standard.interactive_learning",
            )
            QtWidgets.QMessageBox.information(
                self,
                "Model Reset",
                "Interactive learning model has been reset.\n"
                "All training examples have been cleared.",
            )
    def _on_annotation_space_changed(self, value: str) -> None:
        """Switch annotation space between stack and projection contexts."""
        old_space = str(getattr(self.controller.session_state, "annotation_space", "stack")).strip().lower()
        space = str(value or "stack").strip().lower()
        if space not in ("stack", "projection"):
            space = "stack"
        self.controller.set_annotation_space_value(space)
        if old_space != space:
            self._mark_annotation_context_changed(
                f"annotation space changed ({old_space} -> {space})"
            )
        self._status_info(
            f"Annotation space: {space}.",
            timeout_ms=2500,
            source="standard.annotation_space",
        )
        self._refresh_assist_warmup_panel()
        self._update_status()
