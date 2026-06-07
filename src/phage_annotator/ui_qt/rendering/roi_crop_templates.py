"""Extracted method group 4 for RoiCropMixin."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.roi.auto import propose_roi
from phage_annotator.ui_qt.widgets.modality_canvas import LayoutMode



class RoiCropTemplatesMixin:
    """Method group 4 extracted from RoiCropMixin."""

    def _save_roi_template(self) -> None:
        """Save the current ROI as a reusable template (P5.2).
        
        Opens a dialog to name the template, then saves it for later
        application to other images via _apply_roi_template().
        """
        active_roi = self.roi_manager.get_active(self.primary_image.id)
        if active_roi is None or self.roi_rect == (0, 0, 0, 0):
            QtWidgets.QMessageBox.warning(
                self,
                "No ROI to save",
                "Please define an ROI before saving as template."
            )
            return

        # Get template name from user
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            "Save ROI Template",
            "Template name:",
            text=active_roi.name
        )
        if not ok or not name:
            return

        self.roi_manager.save_roi_template(name, active_roi)
        self.recorder.record("save_roi_template", {"name": name})
        QtWidgets.QMessageBox.information(
            self,
            "Template saved",
            f"ROI template '{name}' saved successfully."
        )
    def _apply_roi_template(self, template_name: str = None) -> None:
        """Apply a saved ROI template to the current image (P5.2).
        
        If template_name is None, opens a dialog to select from available templates.
        Otherwise applies the named template directly.
        """
        available = self.roi_manager.list_templates()
        if not available:
            QtWidgets.QMessageBox.warning(
                self,
                "No templates available",
                "Create a template first by saving an ROI."
            )
            return

        # Select template if not provided
        if template_name is None:
            template_name, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Apply ROI Template",
                "Select template:",
                available
            )
            if not ok or not template_name:
                return

        # Apply template
        if self.roi_manager.apply_template_to_image(template_name, self.primary_image.id):
            # Update UI
            new_roi = self.roi_manager.get_active(self.primary_image.id)
            if new_roi:
                rect = (
                    new_roi.points[0][0] if new_roi.points else 0,
                    new_roi.points[0][1] if new_roi.points else 0,
                    new_roi.points[1][0] - new_roi.points[0][0] if len(new_roi.points) > 1 else 100,
                    new_roi.points[1][1] - new_roi.points[0][1] if len(new_roi.points) > 1 else 100,
                )
                self.controller.set_roi(rect, shape=new_roi.roi_type)
                self._sync_roi_controls()
                self._request_ui_refresh("roi-crop")
                self.recorder.record("apply_roi_template", {"template": template_name})
                QtWidgets.QMessageBox.information(
                    self,
                    "Template applied",
                    f"Applied template '{template_name}' to current image."
                )
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Template not found",
                f"Template '{template_name}' could not be found."
            )
