"""Split definitions from test_qc_export.py."""

from __future__ import annotations

import json
import tempfile
from csv import DictReader
from pathlib import Path
from typing import List

import pytest

from phage_annotator.analysis.qc_validators import QCIssue, IssueSeverity
from phage_annotator.io.qc_export import QCReportExporter


@pytest.fixture
def sample_issues() -> List[QCIssue]:
    """Create sample QC issues for testing."""
    return [
        QCIssue(
            issue_id="dup_001",
            severity=IssueSeverity.ERROR,
            issue_type="duplicate",
            message="Duplicate annotations at (100, 200)",
            image_id="img_001",
            affected_annotation_ids=["ann_1", "ann_2"],
            location_x=100,
            location_y=200,
            location_z=5,
            location_t=10,
        ),
        QCIssue(
            issue_id="bound_001",
            severity=IssueSeverity.WARNING,
            issue_type="out_of_bounds",
            message="Annotation outside image bounds",
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
            message="Annotation has no label",
            image_id="img_001",
            affected_annotation_ids=["ann_4"],
            location_x=150,
            location_y=250,
            location_z=3,
            location_t=5,
        ),
    ]
