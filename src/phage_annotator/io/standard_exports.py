"""Standardized export adapters for interoperability and review workflows."""

from __future__ import annotations

import csv
import json
import pathlib
import time
from dataclasses import asdict
from typing import Dict, Iterable, List, Sequence

from phage_annotator.analysis.reviewer_analytics import (
    compute_issue_trend,
    compute_reviewer_metrics,
)
from phage_annotator.core.annotation import Keypoint


def validate_keypoints_for_export(keypoints: Sequence[Keypoint]) -> list[str]:
    """Return validation errors for export preflight."""
    errors: list[str] = []
    for idx, kp in enumerate(keypoints):
        if kp.image_id is None or int(kp.image_id) < 0:
            errors.append(f"row {idx}: invalid image_id {kp.image_id}")
        if kp.label is None or not str(kp.label).strip():
            errors.append(f"row {idx}: missing label")
        if kp.annotation_id is None or not str(kp.annotation_id).strip():
            errors.append(f"row {idx}: missing annotation_id")
    return errors


def export_canonical_csv(keypoints: Sequence[Keypoint], path: pathlib.Path) -> None:
    """Export keypoints with stable, explicit fields suitable for pipelines."""
    rows = []
    for kp in keypoints:
        rows.append(
            {
                "annotation_id": kp.annotation_id,
                "image_id": int(kp.image_id),
                "image_name": kp.image_name,
                "t": int(kp.t),
                "z": int(kp.z),
                "x": float(kp.x),
                "y": float(kp.y),
                "label": kp.label,
                "modality_idx": kp.modality_idx,
                "source": kp.source,
                "meta_json": json.dumps(dict(kp.meta), sort_keys=True),
            }
        )

    fieldnames = list(rows[0].keys()) if rows else [
        "annotation_id",
        "image_id",
        "image_name",
        "t",
        "z",
        "x",
        "y",
        "label",
        "modality_idx",
        "source",
        "meta_json",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def export_canonical_json(keypoints: Sequence[Keypoint], path: pathlib.Path) -> None:
    """Export keypoints in a deterministic canonical JSON envelope."""
    payload = {
        "schema": "phage_annotator.canonical_keypoints",
        "schema_version": 1,
        "export_timestamp": time.time(),
        "count": len(keypoints),
        "annotations": [asdict(kp) for kp in keypoints],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_coco_keypoints(
    keypoints: Sequence[Keypoint],
    image_records: Sequence[dict],
    path: pathlib.Path,
) -> None:
    """Export a simple COCO keypoints-style payload.

    Notes
    -----
    This tool stores one point per annotation. Each annotation is exported as a
    one-keypoint instance with a tiny bounding box centered at (x, y).
    """
    categories_by_label: Dict[str, int] = {}
    categories: list[dict] = []

    def _category_id(label: str) -> int:
        if label not in categories_by_label:
            cid = len(categories_by_label) + 1
            categories_by_label[label] = cid
            categories.append(
                {
                    "id": cid,
                    "name": label,
                    "supercategory": "phage_annotation",
                    "keypoints": ["point"],
                    "skeleton": [],
                }
            )
        return categories_by_label[label]

    images: list[dict] = []
    for rec in image_records:
        images.append(
            {
                "id": int(rec["id"]),
                "file_name": str(rec.get("file_name", "")),
                "width": int(rec.get("width", 0)),
                "height": int(rec.get("height", 0)),
            }
        )

    annotations: list[dict] = []
    for idx, kp in enumerate(keypoints, start=1):
        cat_id = _category_id(kp.label)
        x = float(kp.x)
        y = float(kp.y)
        bbox = [x - 1.0, y - 1.0, 2.0, 2.0]
        annotations.append(
            {
                "id": idx,
                "image_id": int(kp.image_id),
                "category_id": cat_id,
                "keypoints": [x, y, 2],
                "num_keypoints": 1,
                "bbox": bbox,
                "area": 4.0,
                "iscrowd": 0,
                "attributes": {
                    "t": int(kp.t),
                    "z": int(kp.z),
                    "annotation_id": kp.annotation_id,
                    "meta": dict(kp.meta),
                },
            }
        )

    payload = {
        "info": {
            "description": "Phage Annotator COCO keypoints export",
            "version": "1.0",
            "year": time.gmtime().tm_year,
        },
        "images": images,
        "annotations": annotations,
        "categories": categories,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_evidence_bundle(
    output_dir: pathlib.Path,
    *,
    keypoints: Sequence[Keypoint],
    qc_issues: Sequence[object],
    audit_log: Sequence[dict],
    suggestion_metrics: dict,
) -> pathlib.Path:
    """Write a review evidence bundle directory and return its manifest path."""
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_json = output_dir / "annotations.canonical.json"
    export_canonical_json(keypoints, canonical_json)

    qc_path = output_dir / "qc_issues.json"
    qc_payload = []
    for issue in qc_issues:
        row = {
            "issue_id": getattr(issue, "issue_id", ""),
            "severity": getattr(getattr(issue, "severity", None), "value", ""),
            "issue_type": getattr(issue, "issue_type", ""),
            "message": getattr(issue, "message", ""),
            "image_id": getattr(issue, "image_id", -1),
            "affected_annotation_ids": list(getattr(issue, "affected_annotation_ids", [])),
            "location": {
                "x": getattr(issue, "location_x", None),
                "y": getattr(issue, "location_y", None),
                "z": getattr(issue, "location_z", None),
                "t": getattr(issue, "location_t", None),
            },
        }
        qc_payload.append(row)
    qc_path.write_text(json.dumps(qc_payload, indent=2), encoding="utf-8")

    audit_path = output_dir / "audit_log.json"
    audit_path.write_text(json.dumps(list(audit_log), indent=2), encoding="utf-8")
    reviewer_analytics = {
        "per_user": compute_reviewer_metrics(audit_log),
        "issue_trend": compute_issue_trend(audit_log),
    }
    reviewer_analytics_path = output_dir / "reviewer_analytics.json"
    reviewer_analytics_path.write_text(
        json.dumps(reviewer_analytics, indent=2), encoding="utf-8"
    )

    manifest = {
        "schema": "phage_annotator.evidence_bundle",
        "schema_version": 1,
        "export_timestamp": time.time(),
        "files": {
            "annotations": canonical_json.name,
            "qc_issues": qc_path.name,
            "audit_log": audit_path.name,
            "reviewer_analytics": reviewer_analytics_path.name,
        },
        "summary": {
            "annotation_count": len(keypoints),
            "qc_issue_count": len(qc_payload),
            "audit_event_count": len(audit_log),
            "suggestion_metrics": dict(suggestion_metrics),
        },
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
