"""Split definitions from test_qc_state.py."""

from __future__ import annotations

from typing import List

import pytest

from phage_annotator.analysis.qc_validators import (
    QCIssue,
    IssueSeverity,
)
from phage_annotator.session.qc_state import QCState


from tests.unit.test_qc_state_split1 import sample_issues

@pytest.mark.order(1)
class TestQCStateAffectedAnnotations:
    """Test affected annotation tracking."""
    
    def test_get_affected_annotation_ids(self, sample_issues):
        """Test retrieving all affected annotation IDs."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        affected = state.get_affected_annotation_ids()
        
        # Should have union of all affected IDs
        assert "ann_1" in affected
        assert "ann_2" in affected
        assert "ann_3" in affected
        assert "ann_4" in affected
        assert len(affected) == 4
    
    def test_affected_ids_with_filtering(self, sample_issues):
        """Test affected IDs respects filtering."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable errors
        state.set_filter("error", False)
        
        affected = state.get_affected_annotation_ids(respect_filters=True)
        
        # ann_1 and ann_2 are from error issue
        assert "ann_1" not in affected
        assert "ann_2" not in affected
        # These should still be present
        assert "ann_3" in affected
        assert "ann_4" in affected
    
    def test_affected_ids_ignore_filtering(self, sample_issues):
        """Test that affected IDs can ignore filtering."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable all filters
        state.set_filter("error", False)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        # With respect_filters=False, should still get all
        affected = state.get_affected_annotation_ids(respect_filters=False)
        assert len(affected) == 4
        
        # With respect_filters=True, should get none
        affected = state.get_affected_annotation_ids(respect_filters=True)
        assert len(affected) == 0
    
    def test_overlapping_affected_ids(self):
        """Test with overlapping affected annotations."""
        issue1 = QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=0,
            location_t=0,
        )
        
        issue2 = QCIssue(
            issue_id="dup_002",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate",
            image_id="img_001",
            affected_annotation_ids=["ann_2", "ann_3"],  # Overlaps with issue1
            location_x=150,
            location_y=250,
            location_z=0,
            location_t=0,
        )
        
        state = QCState()
        state.add_issue(issue1)
        state.add_issue(issue2)
        
        affected = state.get_affected_annotation_ids()
        
        # Should have unique union
        assert len(affected) == 3
        assert affected == {"ann_1", "ann_2", "ann_3"}

@pytest.mark.order(1)
class TestQCStateAutomaticValidation:
    """Test automatic validation control."""
    
    def test_auto_validate_flag(self):
        """Test auto_validate flag."""
        state = QCState()
        
        assert state.auto_validate is False
        
        state.auto_validate = True
        assert state.auto_validate is True
    
    def test_validation_timestamp(self):
        """Test validation timestamp tracking."""
        state = QCState()
        
        assert state.validation_timestamp is None
        
        from datetime import datetime
        now = datetime.now()
        state.validation_timestamp = now
        
        assert state.validation_timestamp == now

@pytest.mark.order(2)
class TestQCStateWorkflows:
    """Test QC state in realistic workflows."""
    
    def test_review_workflow(self, sample_issues):
        """Test typical reviewer workflow."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Step 1: Reviewer starts, sees all issues
        assert len(state.get_visible_issues()) == 3
        
        # Step 2: Focus on errors first
        state.set_filter("warning", False)
        state.set_filter("info", False)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "duplicate"
        
        # Step 3: After dealing with errors, look at warnings
        state.set_filter("error", False)
        state.set_filter("warning", True)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "out_of_bounds"
        
        # Step 4: Review info messages
        state.set_filter("warning", False)
        state.set_filter("info", True)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].issue_type == "missing_label"
    
    def test_export_report_workflow(self, sample_issues):
        """Test workflow for generating report."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Get all issues regardless of filter state
        report_issues = state.get_visible_issues(ignore_filters=True)
        assert len(report_issues) == 3
        
        # Count by severity
        error_count = sum(1 for i in report_issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in report_issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in report_issues if i.severity == IssueSeverity.INFO)
        
        assert error_count == 1
        assert warning_count == 1
        assert info_count == 1
    
    def test_batch_fix_workflow(self, sample_issues):
        """Test workflow for batch fixing issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Get all annotations that need attention
        affected = state.get_affected_annotation_ids(respect_filters=False)
        assert len(affected) == 4
        
        # Simulate fixing some annotations
        # Clear and add back only remaining issues
        remaining_issues = [issue for issue in sample_issues if "ann_1" not in issue.affected_annotation_ids]
        
        state.clear_issues()
        for issue in remaining_issues:
            state.add_issue(issue)
        
        affected = state.get_affected_annotation_ids()
        assert "ann_1" not in affected
        assert len(affected) == 2  # ann_3 and ann_4
