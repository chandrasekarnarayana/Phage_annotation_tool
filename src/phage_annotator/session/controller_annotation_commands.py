"""Controller helpers exposing command-backed annotation and QC operations."""

from __future__ import annotations

from phage_annotator.session.batch_commands import (
    BatchAssignLabelCommand,
    BatchDeleteDuplicatesCommand,
    BatchDeleteOutOfBoundsCommand,
    BatchReviewDensityClustersCommand,
)
from phage_annotator.session.metadata_commands import (
    BulkUpdateMetadataCommand,
    UpdateLabelCommand,
    UpdateMetadataCommand,
)


class SessionControllerAnnotationCommandsMixin:
    """Controller helpers for command-backed annotation updates and QC actions."""

    def get_qc_issues(
        self,
        *,
        issue_type: str | None = None,
        image_ids: list[int] | None = None,
    ) -> list[object]:
        """Return QC issues filtered by type and optional image ids."""
        allowed = {int(i) for i in list(image_ids or [])} if image_ids else None
        desired = str(issue_type or "").strip().lower()
        rows = list(getattr(self.session_state, "qc_issues", []) or [])
        return [
            issue
            for issue in rows
            if (not desired or str(getattr(issue, "issue_type", "")).strip().lower() == desired)
            and (allowed is None or int(getattr(issue, "image_id", -1)) in allowed)
        ]

    def update_annotation_metadata(self, image_id: int, point_id: str, field: str, value: object) -> bool:
        """Execute a metadata update on the controller command stack."""
        return bool(
            self.execute_view_command(
                UpdateMetadataCommand(
                    self,
                    image_id=int(image_id),
                    annotation_id=str(point_id),
                    field_name=str(field),
                    new_value=value,
                )
            )
        )

    def bulk_update_annotation_metadata(self, image_id: int, updates: list[dict]) -> bool:
        """Execute bulk metadata updates on the controller command stack."""
        return bool(
            self.execute_view_command(
                BulkUpdateMetadataCommand(self, image_id=int(image_id), updates=list(updates or []))
            )
        )

    def update_annotation_label(self, image_id: int, point_id: str, new_label: str) -> bool:
        """Execute a label update on the controller command stack."""
        return bool(
            self.execute_view_command(
                UpdateLabelCommand(
                    self,
                    image_id=int(image_id),
                    annotation_id=str(point_id),
                    new_label=str(new_label),
                )
            )
        )

    def batch_delete_duplicate_annotations(self, image_ids: list[int] | None = None) -> bool:
        """Run duplicate-annotation cleanup as an undoable batch command."""
        issues = self.get_qc_issues(issue_type="duplicate", image_ids=image_ids)
        return bool(self.execute_view_command(BatchDeleteDuplicatesCommand(self, duplicate_issues=issues)))

    def batch_delete_out_of_bounds_annotations(self, image_ids: list[int] | None = None) -> bool:
        """Run out-of-bounds cleanup as an undoable batch command."""
        issues = self.get_qc_issues(issue_type="out_of_bounds", image_ids=image_ids)
        return bool(self.execute_view_command(BatchDeleteOutOfBoundsCommand(self, out_of_bounds_issues=issues)))

    def batch_assign_missing_labels(
        self,
        default_label: str = "Unknown",
        image_ids: list[int] | None = None,
    ) -> bool:
        """Run missing-label assignment as an undoable batch command."""
        issues = self.get_qc_issues(issue_type="missing_label", image_ids=image_ids)
        return bool(
            self.execute_view_command(
                BatchAssignLabelCommand(self, missing_label_issues=issues, default_label=str(default_label))
            )
        )

    def batch_review_density_clusters(
        self,
        mark_as_reviewed: bool = True,
        image_ids: list[int] | None = None,
    ) -> bool:
        """Run density-cluster review as an undoable batch command."""
        issues = self.get_qc_issues(issue_type="density_cluster", image_ids=image_ids)
        return bool(
            self.execute_view_command(
                BatchReviewDensityClustersCommand(
                    self,
                    density_issues=issues,
                    mark_as_reviewed=bool(mark_as_reviewed),
                )
            )
        )
