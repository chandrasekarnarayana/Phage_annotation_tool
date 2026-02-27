"""Batch operation commands for QC issue resolution (M6)."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from phage_annotator.session.commands import Command, TransactionCommand

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController
    from phage_annotator.analysis.qc_validators import QCIssue


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
        self.controller = controller
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
            transaction = TransactionCommand(commands)
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
        self.controller = controller
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
            transaction = TransactionCommand(commands)
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


class BatchAssignLabelCommand(Command):
    """Command to assign labels to annotations missing labels."""
    
    def __init__(
        self,
        controller: "SessionController",
        missing_label_issues: List["QCIssue"],
        default_label: str,
    ):
        """Initialize batch assign label command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller managing annotations.
        missing_label_issues : list of QCIssue
            Missing label issues to resolve.
        default_label : str
            Label to assign to unlabeled annotations.
        """
        self.controller = controller
        self.missing_label_issues = missing_label_issues
        self.default_label = default_label
        self.previous_labels = {}  # Store old labels for undo
    
    def execute(self) -> bool:
        """Execute batch label assignment.
        
        Returns
        -------
        bool
            True if successful.
        """
        for issue in self.missing_label_issues:
            if issue.issue_type != "missing_label":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann:
                    # Store old label
                    self.previous_labels[ann_id] = ann.label
                    # Assign new label
                    ann.label = self.default_label
        
        self.controller.session_state.dirty = True
        return True
    
    def undo(self) -> bool:
        """Undo batch label assignment.
        
        Returns
        -------
        bool
            True if successful.
        """
        for issue in self.missing_label_issues:
            if issue.issue_type != "missing_label":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann and ann_id in self.previous_labels:
                    ann.label = self.previous_labels[ann_id]
        
        self.controller.session_state.dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo batch label assignment.
        
        Returns
        -------
        bool
            True if successful.
        """
        return self.execute()


class BatchReviewDensityClustersCommand(Command):
    """Command to mark density clusters as reviewed."""
    
    def __init__(
        self,
        controller: "SessionController",
        density_issues: List["QCIssue"],
        mark_as_reviewed: bool = True,
    ):
        """Initialize batch review density clusters command.
        
        Parameters
        ----------
        controller : SessionController
            Session controller managing annotations.
        density_issues : list of QCIssue
            Density cluster issues to mark as reviewed.
        mark_as_reviewed : bool, default True
            Whether to mark as reviewed (True) or unmark (False).
        """
        self.controller = controller
        self.density_issues = density_issues
        self.mark_as_reviewed = mark_as_reviewed
        self.previous_states = {}  # Store previous review states
    
    def execute(self) -> bool:
        """Execute batch review marking.
        
        Returns
        -------
        bool
            True if successful.
        """
        for issue in self.density_issues:
            if issue.issue_type != "density_cluster":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann:
                    # Store previous state
                    self.previous_states[ann_id] = ann.metadata.get("density_reviewed", False)
                    # Mark as reviewed
                    ann.metadata["density_reviewed"] = self.mark_as_reviewed
        
        self.controller.session_state.dirty = True
        return True
    
    def undo(self) -> bool:
        """Undo batch review marking.
       
        Returns
        -------
        bool
            True if successful.
        """
        for issue in self.density_issues:
            if issue.issue_type != "density_cluster":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann and ann_id in self.previous_states:
                    ann.metadata["density_reviewed"] = self.previous_states[ann_id]
        
        self.controller.session_state.dirty = True
        return True
    
    def redo(self) -> bool:
        """Redo batch review marking.
        
        Returns
        -------
        bool
            True if successful.
        """
        return self.execute()
