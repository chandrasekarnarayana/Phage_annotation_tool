"""Batch operation commands for QC issue resolution (M6)."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from phage_annotator.session.commands import Command, TransactionCommand
from phage_annotator.session.signal_hub import emit_annotations_changed

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController
    from phage_annotator.analysis.qc_validators import QCIssue


def _emit_batch_annotations_changed(controller: "SessionController", image_ids: set[int]) -> None:
    """Publish centralized annotation updates for each affected image."""
    for image_id in sorted(int(i) for i in image_ids):
        emit_annotations_changed(controller, image_id=image_id, change_type="modified")


class BatchDeleteDuplicatesCommand(Command):
    """Command to delete duplicate annotations identified by QC."""
    
    def __init__(
        self,
        controller: "SessionController",
        duplicate_issues: List["QCIssue"],
    ):
        """Initialize batch delete duplicates command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller managing annotations.
        duplicate_issues : list of QCIssue
            Duplicate issues to resolve (keeps first, deletes rest).
        """
        image_id = int(duplicate_issues[0].image_id) if duplicate_issues else -1
        super().__init__(controller, image_id=image_id)
        self.duplicate_issues = duplicate_issues
        self.deleted_annotations = []  # Store for undo
    
    def execute(self) -> bool:
        """Execute batch deletion of duplicate annotations.
        
        For each duplicate group, keep the first annotation and delete the rest.
        
        Returns
        -------
        bool
            True if successful.
        """
        from phage_annotator.session.context_commands import DeleteNearestCommand
        
        commands = []
        
        for issue in self.duplicate_issues:
            if issue.issue_type != "duplicate":
                continue
            
            # Get affected annotations
            affected_ids = issue.affected_annotation_ids
            if len(affected_ids) < 2:
                continue
            
            # Keep first annotation, delete rest
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            # Find annotations to delete (skip first)
            for ann_id in affected_ids[1:]:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann:
                    # Create delete command for this annotation
                    delete_cmd = DeleteNearestCommand(
                        controller=self.controller,
                        image_id=image_id,
                        x=ann.x,
                        y=ann.y,
                        radius=1.0,  # Exact match
                    )
                    commands.append(delete_cmd)
        
        # Execute as transaction
        if commands:
            transaction = TransactionCommand(
                self.controller,
                image_id=int(commands[0].image_id),
                transaction_name="Batch delete duplicates",
            )
            for cmd in commands:
                transaction.add_command(cmd)
            transaction.execute()
            self.deleted_annotations = commands  # Store for undo
        
        return True
    
    def undo(self) -> bool:
        """Undo batch deletion.
        
        Returns
        -------
        bool
            True if successful.
        """
        # Undo each delete command
        for cmd in reversed(self.deleted_annotations):
            cmd.undo()
        return True
    
    def redo(self) -> bool:
        """Redo batch deletion.
        
        Returns
        -------
        bool
            True if successful.
        """
        # Redo each delete command
        for cmd in self.deleted_annotations:
            cmd.redo()
        return True

    def emit_change_signals(self) -> None:
        """Sub-commands publish annotation changes internally."""
        return None


class BatchDeleteOutOfBoundsCommand(Command):
    """Command to delete out-of-bounds annotations identified by QC."""
    
    def __init__(
        self,
        controller: "SessionController",
        out_of_bounds_issues: List["QCIssue"],
    ):
        """Initialize batch delete out-of-bounds command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller managing annotations.
        out_of_bounds_issues : list of QCIssue
            Out-of-bounds issues to resolve.
        """
        image_id = int(out_of_bounds_issues[0].image_id) if out_of_bounds_issues else -1
        super().__init__(controller, image_id=image_id)
        self.out_of_bounds_issues = out_of_bounds_issues
        self.deleted_annotations = []  # Store for undo
    
    def execute(self) -> bool:
        """Execute batch deletion of out-of-bounds annotations.
        
        Returns
        -------
        bool
            True if successful.
        """
        from phage_annotator.session.context_commands import DeleteNearestCommand
        
        commands = []
        
        for issue in self.out_of_bounds_issues:
            if issue.issue_type != "out_of_bounds":
                continue
            
            # Get affected annotation
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann:
                    # Create delete command
                    delete_cmd = DeleteNearestCommand(
                        controller=self.controller,
                        image_id=image_id,
                        x=ann.x,
                        y=ann.y,
                        radius=1.0,  # Exact match
                    )
                    commands.append(delete_cmd)
        
        # Execute as transaction
        if commands:
            transaction = TransactionCommand(
                self.controller,
                image_id=int(commands[0].image_id),
                transaction_name="Batch delete out-of-bounds",
            )
            for cmd in commands:
                transaction.add_command(cmd)
            transaction.execute()
            self.deleted_annotations = commands
        
        return True
    
    def undo(self) -> bool:
        """Undo batch deletion.
        
        Returns
        -------
        bool
            True if successful.
        """
        for cmd in reversed(self.deleted_annotations):
            cmd.undo()
        return True
    
    def redo(self) -> bool:
        """Redo batch deletion.
        
        Returns
        -------
        bool
            True if successful.
        """
        for cmd in self.deleted_annotations:
            cmd.redo()
        return True

    def emit_change_signals(self) -> None:
        """Sub-commands publish annotation changes internally."""
        return None



from phage_annotator.session.batch_label_commands import (
    BatchAssignLabelCommand, BatchReviewDensityClustersCommand,
)

__all__ = [
    "BatchDeleteDuplicatesCommand", "BatchDeleteOutOfBoundsCommand",
    "BatchAssignLabelCommand", "BatchReviewDensityClustersCommand",
]
