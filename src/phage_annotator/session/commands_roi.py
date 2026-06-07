"""Undo/redo command framework for view state changes.

This module extends the existing annotation undo/redo system to support
view state operations like ROI changes, crop operations, display mapping
adjustments, and threshold parameter changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Tuple

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController

from phage_annotator.session.signal_hub import (
    annotation_notification_batch,
    emit_display_changed,
    emit_roi_changed,
    emit_state_changed,
    emit_view_changed,
)
from phage_annotator.session.commands_base import Command, CommandMemento


@dataclass





class SetROICommand(Command):
    """Command to change ROI (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_roi_shape: str,
        new_roi_rect: Tuple[float, float, float, float],
    ):
        """Document the init flow."""
        super().__init__(controller, image_id)
        self.new_roi_shape = new_roi_shape
        self.new_roi_rect = new_roi_rect
    
    def execute(self) -> bool:
        # Capture current state
        """Document the execute flow."""
        view_state = self.controller.view_state
        self.memento_before = CommandMemento(
            command_type="set_roi",
            image_id=self.image_id,
            data={
                "roi_shape": view_state.roi_shape,
                "roi_rect": view_state.roi_rect,
            },
        )
        
        # Apply new state
        view_state.roi_shape = self.new_roi_shape
        view_state.roi_rect = self.new_roi_rect
        
        # Capture after state
        self.memento_after = CommandMemento(
            command_type="set_roi",
            image_id=self.image_id,
            data={
                "roi_shape": self.new_roi_shape,
                "roi_rect": self.new_roi_rect,
            },
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        view_state = self.controller.view_state
        view_state.roi_shape = self.memento_before.data["roi_shape"]
        view_state.roi_rect = self.memento_before.data["roi_rect"]
        return True
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        view_state = self.controller.view_state
        view_state.roi_shape = self.memento_after.data["roi_shape"]
        view_state.roi_rect = self.memento_after.data["roi_rect"]
        return True

    def emit_change_signals(self) -> None:
        """Document the emit_change_signals flow."""
        rect = tuple(self.controller.view_state.roi_rect)
        emit_view_changed(self.controller, change_type="roi", roi_rect=rect)
        emit_roi_changed(self.controller)



class SetCropCommand(Command):
    """Command to change crop region (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_crop_rect: Optional[Tuple[float, float, float, float]],
    ):
        """Document the init flow."""
        super().__init__(controller, image_id)
        self.new_crop_rect = new_crop_rect
    
    def execute(self) -> bool:
        """Document the execute flow."""
        view_state = self.controller.view_state
        self.memento_before = CommandMemento(
            command_type="set_crop",
            image_id=self.image_id,
            data={"crop_rect": view_state.crop_rect},
        )
        
        view_state.crop_rect = self.new_crop_rect
        
        self.memento_after = CommandMemento(
            command_type="set_crop",
            image_id=self.image_id,
            data={"crop_rect": self.new_crop_rect},
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        self.controller.view_state.crop_rect = self.memento_before.data["crop_rect"]
        return True
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        self.controller.view_state.crop_rect = self.memento_after.data["crop_rect"]
        return True

    def emit_change_signals(self) -> None:
        """Document the emit_change_signals flow."""
        emit_view_changed(
            self.controller,
            change_type="crop",
            crop_rect=self.controller.view_state.crop_rect,
        )


class SetCropFromRoiCommand(SetCropCommand):
    """Command to set the crop rectangle from the current ROI rectangle."""

    def __init__(self, controller: "SessionController", image_id: int):
        """Capture the current ROI rectangle as the target crop."""
        roi_rect = tuple(getattr(controller.view_state, "roi_rect", (0.0, 0.0, 0.0, 0.0)))
        super().__init__(controller, image_id, roi_rect)

    def execute(self) -> bool:
        """Apply the current ROI rectangle as crop when it is valid."""
        roi_shape = str(getattr(self.controller.view_state, "roi_shape", "none"))
        roi_rect = tuple(getattr(self.controller.view_state, "roi_rect", (0.0, 0.0, 0.0, 0.0)))
        if roi_shape == "none" or len(roi_rect) != 4 or roi_rect[2] <= 0 or roi_rect[3] <= 0:
            return False
        self.new_crop_rect = roi_rect
        return super().execute()
