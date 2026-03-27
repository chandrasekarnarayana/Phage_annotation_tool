"""Export and reviewer analytics actions."""

from __future__ import annotations

import json
import pathlib
import time

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.analysis.reviewer_analytics import (
    build_reviewer_dashboard_text,
    compute_issue_trend,
    compute_reviewer_metrics,
)
from phage_annotator.analysis.suggestion_ranker import dataset_metrics_from_suggestions
from phage_annotator.io.standard_exports import (
    export_canonical_csv,
    export_canonical_json,
    export_coco_keypoints,
    export_evidence_bundle,
    validate_keypoints_for_export,
)


class ExportActionsMixin:
    """Standard-export and reviewer analytics dialogs."""

    def _export_standard_bundle_dialog(self) -> None:
        """Export standardized formats with schema preset selection."""
        all_points = []
        for image_id in sorted(self.annotations.keys()):
            all_points.extend(self.annotations.get(image_id, []))
        errors = validate_keypoints_for_export(all_points)
        if errors:
            QtWidgets.QMessageBox.critical(
                self,
                "Export validation failed",
                "\n".join(errors[:20]),
            )
            return
        preset_options = [
            "COCO Keypoints (.json)",
            "Canonical CSV (.csv)",
            "Canonical JSON (.json)",
            "Evidence Bundle (directory)",
            "All Standard Outputs",
        ]
        preset, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Export Preset",
            "Schema preset:",
            preset_options,
            4,
            False,
        )
        if not ok:
            return
        preset = str(preset)

        image_records = []
        for img in self.images:
            shape = getattr(img, "shape", ())
            if len(shape) >= 2:
                height = int(shape[-2])
                width = int(shape[-1])
            else:
                height, width = 0, 0
            image_records.append(
                {"id": int(img.id), "file_name": str(pathlib.Path(img.path).name), "width": width, "height": height}
            )

        qc_issues = []
        if getattr(self, "qc_state", None) is not None:
            qc_issues = list(self.qc_state.issues)
        outputs: list[str] = []
        if preset in ("COCO Keypoints (.json)", "Canonical JSON (.json)", "Canonical CSV (.csv)"):
            filters = {
                "COCO Keypoints (.json)": "JSON Files (*.json)",
                "Canonical JSON (.json)": "JSON Files (*.json)",
                "Canonical CSV (.csv)": "CSV Files (*.csv)",
            }
            target_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Select export file", str(pathlib.Path.cwd()), filters[preset]
            )
            if not target_path:
                return
            output = pathlib.Path(target_path)
            if preset == "COCO Keypoints (.json)":
                export_coco_keypoints(all_points, image_records, output)
            elif preset == "Canonical JSON (.json)":
                export_canonical_json(all_points, output)
            else:
                export_canonical_csv(all_points, output)
            outputs.append(output.name)
            root_output = output.parent
        else:
            output_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Select export folder", str(pathlib.Path.cwd())
            )
            if not output_dir:
                return
            root_output = pathlib.Path(output_dir)
            root_output.mkdir(parents=True, exist_ok=True)

            if preset in ("All Standard Outputs", "Evidence Bundle (directory)"):
                bundle_dir = root_output / "evidence_bundle"
                manifest = export_evidence_bundle(
                    bundle_dir,
                    keypoints=all_points,
                    qc_issues=qc_issues,
                    audit_log=list(self.controller.session_state.audit_log),
                    suggestion_metrics=dict(self.controller.session_state.suggestion_metrics),
                )
                outputs.append(str(manifest.relative_to(root_output)))
            if preset == "All Standard Outputs":
                canonical_csv = root_output / "annotations.canonical.csv"
                canonical_json = root_output / "annotations.canonical.json"
                coco_json = root_output / "annotations.coco.keypoints.json"
                export_canonical_csv(all_points, canonical_csv)
                export_canonical_json(all_points, canonical_json)
                export_coco_keypoints(all_points, image_records, coco_json)
                outputs.extend([canonical_csv.name, canonical_json.name, coco_json.name])

        self.controller.append_audit_event(
            "standard_export_completed",
            output_dir=str(root_output),
            preset=preset,
            files=outputs,
        )
        self._status_success(
            f"Exported {len(outputs)} output(s) to {root_output}.",
            timeout_ms=4000,
            source="export.standard_bundle",
        )

    def _show_reviewer_analytics_dialog(self) -> None:
        """Display per-user metrics and QC trend from audit history."""
        audit_log = list(self.controller.session_state.audit_log)
        summary = build_reviewer_dashboard_text(audit_log)
        per_user = compute_reviewer_metrics(audit_log)
        issue_trend = compute_issue_trend(audit_log)

        all_suggestions = []
        for rows in getattr(self.controller.session_state, "suggestion_history", {}).values():
            all_suggestions.extend(rows)
        proposal_metrics = dataset_metrics_from_suggestions(
            all_suggestions,
            threshold=float(getattr(self, "_suggestion_score_threshold", 0.5)),
            baseline_points_per_min=50.0,
        )
        per_dataset_metrics = {}
        for suggestion in all_suggestions:
            dataset = str(getattr(suggestion, "image_name", "unknown"))
            per_dataset_metrics.setdefault(dataset, []).append(suggestion)
        per_dataset_metrics = {
            name: dataset_metrics_from_suggestions(
                rows,
                threshold=float(getattr(self, "_suggestion_score_threshold", 0.5)),
                baseline_points_per_min=50.0,
            )
            for name, rows in per_dataset_metrics.items()
        }

        payload = {
            "generated_at": time.time(),
            "per_user": per_user,
            "issue_trend": issue_trend,
            "proposal_metrics": proposal_metrics,
            "proposal_metrics_per_dataset": per_dataset_metrics,
        }
        summary += (
            "\n\nProposal Metrics\n================\n"
            f"- Precision@threshold: {proposal_metrics['precision_at_threshold']:.3f}\n"
            f"- Acceptance rate: {proposal_metrics['acceptance_rate']:.3f}\n"
            f"- Estimated time saved (minutes): {proposal_metrics['estimated_time_saved_minutes']:.2f}\n"
            "- confidence = calibrated p_accept from the ranker\n"
            "- generator score = heuristic score\n"
            "- Calibration is dataset-dependent; p_accept is meaningful only under similar acquisition conditions.\n"
        )
        if per_dataset_metrics:
            summary += "\nAcceptance rate per dataset:\n"
            for name, row in sorted(per_dataset_metrics.items()):
                summary += f"- {name}: {row['acceptance_rate']:.3f}\n"

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Reviewer Analytics")
        dlg.resize(760, 520)
        layout = QtWidgets.QVBoxLayout(dlg)
        text = QtWidgets.QPlainTextEdit(dlg)
        text.setReadOnly(True)
        text.setPlainText(summary)
        layout.addWidget(text)

        export_btn = QtWidgets.QPushButton("Export Analytics JSON…", dlg)
        close_btn = QtWidgets.QPushButton("Close", dlg)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(export_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        def _export() -> None:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                dlg,
                "Export analytics",
                str(pathlib.Path.cwd() / "reviewer_analytics.json"),
                "JSON Files (*.json)",
            )
            if not path:
                return
            pathlib.Path(path).write_text(
                json.dumps(payload, indent=2),
                encoding="utf-8",
            )
            self._status_success(
                f"Reviewer analytics exported to {path}.",
                timeout_ms=4000,
                source="export.reviewer_analytics",
            )

        export_btn.clicked.connect(_export)
        close_btn.clicked.connect(dlg.accept)
        dlg.exec()
