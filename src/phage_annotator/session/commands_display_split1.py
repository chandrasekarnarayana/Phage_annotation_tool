"""Split definitions from commands_display.py."""

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





class SetDisplayMappingCommand(Command):
    """Command to change display mapping (vmin/vmax/gamma) (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        panel: str,
        new_vmin: float,
        new_vmax: float,
        new_gamma: float,
    ):
        """Document the init flow."""
        super().__init__(controller, image_id)
        self.panel = panel
        self.new_vmin = new_vmin
        self.new_vmax = new_vmax
        self.new_gamma = new_gamma
    
    def execute(self) -> bool:
        """Document the execute flow."""
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        self.memento_before = CommandMemento(
            command_type="set_display_mapping",
            image_id=self.image_id,
            data={
                "panel": self.panel,
                "vmin": float(mapping.min_val),
                "vmax": float(mapping.max_val),
                "gamma": float(mapping.gamma),
            },
        )
        
        mapping.set_window(self.new_vmin, self.new_vmax)
        mapping.gamma = self.new_gamma
        
        self.memento_after = CommandMemento(
            command_type="set_display_mapping",
            image_id=self.image_id,
            data={
                "panel": self.panel,
                "vmin": self.new_vmin,
                "vmax": self.new_vmax,
                "gamma": self.new_gamma,
            },
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        mapping.set_window(
            self.memento_before.data["vmin"],
            self.memento_before.data["vmax"],
        )
        mapping.gamma = self.memento_before.data["gamma"]
        return True
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        mapping = self.controller.display_mapping.mapping_for(self.image_id, self.panel)
        mapping.set_window(
            self.memento_after.data["vmin"],
            self.memento_after.data["vmax"],
        )
        mapping.gamma = self.memento_after.data["gamma"]
        return True

    def emit_change_signals(self) -> None:
        """Document the emit_change_signals flow."""
        emit_display_changed(self.controller)

class SetThresholdCommand(Command):
    """Command to change threshold parameters (P3.1)."""
    
    def __init__(
        self,
        controller: "SessionController",
        image_id: int,
        new_settings: dict,
    ):
        """Document the init flow."""
        super().__init__(controller, image_id)
        self.new_settings = new_settings
    
    def execute(self) -> bool:
        # Get current threshold settings for this image
        """Document the execute flow."""
        current = self.controller.session_state.threshold_configs_by_image.get(
            self.image_id, {}
        )
        self.memento_before = CommandMemento(
            command_type="set_threshold",
            image_id=self.image_id,
            data={"settings": dict(current)},
        )
        
        # Apply new settings
        self.controller.session_state.threshold_configs_by_image[self.image_id] = (
            dict(self.new_settings)
        )
        
        self.memento_after = CommandMemento(
            command_type="set_threshold",
            image_id=self.image_id,
            data={"settings": dict(self.new_settings)},
        )
        return True
    
    def undo(self) -> bool:
        """Document the undo flow."""
        if not self.memento_before:
            return False
        self.controller.session_state.threshold_configs_by_image[self.image_id] = dict(
            self.memento_before.data["settings"]
        )
        return True
    
    def redo(self) -> bool:
        """Document the redo flow."""
        if not self.memento_after:
            return False
        self.controller.session_state.threshold_configs_by_image[self.image_id] = dict(
            self.memento_after.data["settings"]
        )
        return True

    def emit_change_signals(self) -> None:
        """Document the emit_change_signals flow."""
        emit_state_changed(self.controller)
