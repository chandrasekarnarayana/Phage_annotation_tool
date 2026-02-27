"""QC issue state management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity


@dataclass
class QCState:
    """State for QC issues and validation."""
    
    issues: List[QCIssue] = field(default_factory=list)
    validation_timestamp: Optional[float] = None
    auto_validate: bool = False  # Run validation after edits
    filters: Dict[str, bool] = field(default_factory=lambda: {
        "error": True,
        "warning": True,
        "info": True,  # All visible by default
    })
    
    def add_issue(self, issue: QCIssue) -> None:
        """Add an issue to the state."""
        self.issues.append(issue)
    
    def clear_issues(self) -> None:
        """Clear all issues."""
        self.issues = []
    
    def get_issues_by_severity(self, severity: IssueSeverity) -> List[QCIssue]:
        """Get issues filtered by severity."""
        return [i for i in self.issues if i.severity == severity]
    
    def get_visible_issues(self, respect_filters: bool = True, ignore_filters: bool = False) -> List[QCIssue]:
        """Get issues that pass current filters.
        
        Parameters
        ----------
        respect_filters : bool, default True
            Apply current filter settings to results.
        ignore_filters : bool, default False
            Ignore filter settings and return all issues (overrides respect_filters).
        
        Returns
        -------
        list of QCIssue
            Visible issues based on filtering.
        """
        if ignore_filters or not respect_filters:
            return self.issues.copy()
        
        visible = []
        for issue in self.issues:
            severity_key = issue.severity.value
            if self.filters.get(severity_key, True):
                visible.append(issue)
        return visible
    
    def set_filter(self, severity: str, visible: bool) -> None:
        """Toggle visibility of issues by severity."""
        valid_severities = ["error", "warning", "info"]
        if severity in valid_severities:
            self.filters[severity] = visible
    
    def get_affected_annotation_ids(self, respect_filters: bool = False) -> set:
        """Get all annotation IDs with issues.
        
        Parameters
        ----------
        respect_filters : bool, default False
            Only include IDs from visible issues (respecting filter settings).
        
        Returns
        -------
        set
            Set of affected annotation IDs.
        """
        issues_to_check = self.get_visible_issues(respect_filters=respect_filters) if respect_filters else self.issues
        ids = set()
        for issue in issues_to_check:
            ids.update(issue.affected_annotation_ids)
        return ids
