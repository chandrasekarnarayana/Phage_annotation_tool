"""Batch label and density-cluster commands for QC issue resolution."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from phage_annotator.session.commands import Command, TransactionCommand
from phage_annotator.session.signal_hub import emit_annotations_changed

if TYPE_CHECKING:
    from phage_annotator.session.controller import SessionController
    from phage_annotator.analysis.qc_validators import QCIssue


def _emit_batch_annotations_changed(controller: "SessionController", image_ids: set[int]) -> None:
    """Document the emit_batch_annotations_changed flow."""
    for image_id in sorted(int(i) for i in image_ids):
        emit_annotations_changed(controller, image_id=image_id, change_type="modified")


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
        image_id = int(missing_label_issues[0].image_id) if missing_label_issues else -1
        super().__init__(controller, image_id=image_id)
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
        changed_image_ids: set[int] = set()
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
                    changed_image_ids.add(int(image_id))

        if changed_image_ids:
            _emit_batch_annotations_changed(self.controller, changed_image_ids)
        return True
    
    def undo(self) -> bool:
        """Undo batch label assignment.
        
        Returns
        -------
        bool
            True if successful.
        """
        changed_image_ids: set[int] = set()
        for issue in self.missing_label_issues:
            if issue.issue_type != "missing_label":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann and ann_id in self.previous_labels:
                    ann.label = self.previous_labels[ann_id]
                    changed_image_ids.add(int(image_id))

        if changed_image_ids:
            _emit_batch_annotations_changed(self.controller, changed_image_ids)
        return True
    
    def redo(self) -> bool:
        """Redo batch label assignment.
        
        Returns
        -------
        bool
            True if successful.
        """
        return self.execute()

    def emit_change_signals(self) -> None:
        """Batch commands publish annotation changes internally."""
        return None


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
        image_id = int(density_issues[0].image_id) if density_issues else -1
        super().__init__(controller, image_id=image_id)
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
        changed_image_ids: set[int] = set()
        for issue in self.density_issues:
            if issue.issue_type != "density_cluster":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann:
                    # Store previous state
                    self.previous_states[ann_id] = ann.meta.get("density_reviewed", False)
                    # Mark as reviewed
                    ann.meta["density_reviewed"] = self.mark_as_reviewed
                    changed_image_ids.add(int(image_id))

        if changed_image_ids:
            _emit_batch_annotations_changed(self.controller, changed_image_ids)
        return True
    
    def undo(self) -> bool:
        """Undo batch review marking.
       
        Returns
        -------
        bool
            True if successful.
        """
        changed_image_ids: set[int] = set()
        for issue in self.density_issues:
            if issue.issue_type != "density_cluster":
                continue
            
            image_id = issue.image_id
            annotations = self.controller.get_annotations(image_id)
            
            for ann_id in issue.affected_annotation_ids:
                ann = next((a for a in annotations if a.annotation_id == ann_id), None)
                if ann and ann_id in self.previous_states:
                    ann.meta["density_reviewed"] = self.previous_states[ann_id]
                    changed_image_ids.add(int(image_id))

        if changed_image_ids:
            _emit_batch_annotations_changed(self.controller, changed_image_ids)
        return True
    
    def redo(self) -> bool:
        """Redo batch review marking.
        
        Returns
        -------
        bool
            True if successful.
        """
        return self.execute()

    def emit_change_signals(self) -> None:
        """Batch commands publish annotation changes internally."""
        return None
