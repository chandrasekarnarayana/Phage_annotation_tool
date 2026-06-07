"""Split definitions from test_qc_state.py."""

from __future__ import annotations

from typing import List

import pytest

from phage_annotator.analysis.qc_validators import (
    QCIssue,
    IssueSeverity,
)
from phage_annotator.session.qc_state import QCState


@pytest.fixture
def sample_issues() -> List[QCIssue]:
    """Create sample QC issues for testing."""
    return [
        QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate annotations",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=0,
            location_t=0,
        ),
        QCIssue(
            issue_id="bound_001",
            severity=IssueSeverity.WARNING,
            issue_type="out_of_bounds",
            message="Out of bounds",
            image_id="img_001",
            affected_annotation_ids=["ann_3"],
            location_x=2000,
            location_y=2000,
            location_z=0,
            location_t=0,
        ),
        QCIssue(
            issue_id="label_001",
            severity=IssueSeverity.INFO,
            issue_type="missing_label",
            message="Missing label",
            image_id="img_001",
            affected_annotation_ids=["ann_4"],
            location_x=150,
            location_y=250,
            location_z=0,
            location_t=0,
        ),
    ]

@pytest.mark.order(1)
class TestQCStateBasics:
    """Test basic QC state functionality."""
    
    def test_create_empty_state(self):
        """Test creating an empty QC state."""
        state = QCState()
        
        assert state.issues == []
        assert state.validation_timestamp is None
        assert state.auto_validate is False
        assert state.filters is not None
    
    def test_add_issues(self, sample_issues):
        """Test adding issues to state."""
        state = QCState()
        
        for issue in sample_issues:
            state.add_issue(issue)
        
        assert len(state.issues) == 3
        assert state.issues[0].issue_id == "dup_001"
    
    def test_clear_issues(self, sample_issues):
        """Test clearing all issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        assert len(state.issues) == 3
        
        state.clear_issues()
        
        assert len(state.issues) == 0
    
    def test_duplicate_issue_ids(self, sample_issues):
        """Test that duplicate issue IDs are handled."""
        state = QCState()
        
        # Add first issue
        state.add_issue(sample_issues[0])
        assert len(state.issues) == 1
        
        # Add same issue again (by ID)
        state.add_issue(sample_issues[0])
        
        # Should allow duplicates (depends on UI layer to prevent)
        assert len(state.issues) == 2

@pytest.mark.order(1)
class TestQCStateFiltering:
    """Test QC state filtering functionality."""
    
    def test_default_filters(self):
        """Test default filter state."""
        state = QCState()
        
        # All filters should be enabled by default
        assert state.filters.get("error", True) is True
        assert state.filters.get("warning", True) is True
        assert state.filters.get("info", True) is True
    
    def test_set_filter(self):
        """Test setting individual filters."""
        state = QCState()
        
        state.set_filter("error", False)
        assert state.filters["error"] is False
        
        state.set_filter("warning", False)
        assert state.filters["warning"] is False
        
        state.set_filter("error", True)
        assert state.filters["error"] is True
    
    def test_get_visible_issues(self, sample_issues):
        """Test filtering visible issues."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # With all filters enabled, should see all
        visible = state.get_visible_issues()
        assert len(visible) == 3
        
        # Disable errors
        state.set_filter("error", False)
        visible = state.get_visible_issues()
        assert len(visible) == 2
        assert not any(i.severity == IssueSeverity.ERROR for i in visible)
        
        # Disable warnings too
        state.set_filter("warning", False)
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert all(i.severity == IssueSeverity.INFO for i in visible)
    
    def test_toggle_all_filters(self, sample_issues):
        """Test toggling all filters at once."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Disable all
        state.set_filter("error", False)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        visible = state.get_visible_issues()
        assert len(visible) == 0
        
        # Re-enable all
        state.set_filter("error", True)
        state.set_filter("warning", True)
        state.set_filter("info", True)
        
        visible = state.get_visible_issues()
        assert len(visible) == 3
    
    def test_filter_isolated_severity(self, sample_issues):
        """Test filtering to single severity level."""
        state = QCState()
        for issue in sample_issues:
            state.add_issue(issue)
        
        # Show only errors
        state.set_filter("error", True)
        state.set_filter("warning", False)
        state.set_filter("info", False)
        
        visible = state.get_visible_issues()
        assert len(visible) == 1
        assert visible[0].severity == IssueSeverity.ERROR
