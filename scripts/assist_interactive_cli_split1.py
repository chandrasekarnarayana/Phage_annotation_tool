"""Split definitions from assist_interactive_cli.py."""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from tifffile import imread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from phage_annotator.analysis.suggestion_model import LocalPeakSuggestionModel
from phage_annotator.analysis.suggestion_ranker import (
    FEATURE_NAMES,
    LightweightSuggestionRanker,
    feature_vector_from_suggestion,
)


@dataclass
class InteractiveSession:
    image_name: str
    total_suggestions: int = 0
    processed: int = 0
    accepted: int = 0
    rejected: int = 0
    manual_accepted: int = 0
    retrain_events: int = 0
    total_retrain_seconds: float = 0.0
    decision_rows: List[Dict] = field(default_factory=list)
    accepted_annotations: List[Dict] = field(default_factory=list)

def load_ground_truth(csv_path: Path) -> Dict[int, List[Dict[str, float]]]:
    """Load ground truth for the current workflow."""
    gt: Dict[int, List[Dict[str, float]]] = {}
    with csv_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            t_col = "timepoint" if "timepoint" in row else "t"
            t = int(row.get(t_col, 0))
            y = float(row["y"])
            x = float(row["x"])
            gt.setdefault(t, []).append({"y": y, "x": x})
    return gt

def euclidean_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Run the euclidean distance workflow."""
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))

def find_nearest_gt(
    suggestion_pos: Tuple[float, float], gt_points: List[Dict], distance_threshold: float = 5.0
) -> Tuple[bool, float]:
    """Find nearest gt for the current workflow."""
    if not gt_points:
        return False, float("inf")
    distances = [euclidean_distance(suggestion_pos, (g["y"], g["x"])) for g in gt_points]
    min_dist = min(distances)
    return min_dist <= distance_threshold, min_dist

def greedy_match_count(points: List[Tuple[float, float]], gt_points: List[Dict], threshold: float = 5.0) -> int:
    """Run the greedy match count workflow."""
    if not points or not gt_points:
        return 0
    unmatched = set(range(len(gt_points)))
    matched = 0
    for py, px in points:
        best_idx = None
        best_dist = float("inf")
        for idx in unmatched:
            gy, gx = float(gt_points[idx]["y"]), float(gt_points[idx]["x"])
            dist = euclidean_distance((py, px), (gy, gx))
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is not None and best_dist <= threshold:
            unmatched.remove(best_idx)
            matched += 1
    return matched

def parse_manual_points(text: str) -> List[Tuple[float, float]]:
    """Parse manual points for the current workflow."""
    text = (text or "").strip()
    if not text:
        return []
    points: List[Tuple[float, float]] = []
    for token in text.split(";"):
        token = token.strip()
        if not token:
            continue
        parts = [p.strip() for p in token.split(",")]
        if len(parts) != 2:
            continue
        try:
            y = float(parts[0])
            x = float(parts[1])
            points.append((y, x))
        except ValueError:
            continue
    return points

def nearest_suggestion_for_features(
    point: Tuple[float, float], suggestions: List, max_dist_px: float = 8.0
):
    """Run the nearest suggestion for features workflow."""
    best = None
    best_dist = float("inf")
    for s in suggestions:
        dist = euclidean_distance(point, (float(s.y), float(s.x)))
        if dist < best_dist:
            best = s
            best_dist = dist
    if best is not None and best_dist <= max_dist_px:
        return best
    return None

def decision_row_from_suggestion(
    *,
    iteration: int,
    decision_id: int,
    is_accepted: bool,
    suggestion,
    decision_source: str,
    gt_points: List[Dict],
) -> Dict:
    """Run the decision row from suggestion workflow."""
    is_match, distance = find_nearest_gt((float(suggestion.y), float(suggestion.x)), gt_points)
    row = {
        "decision_id": decision_id,
        "iteration": iteration,
        "decision_source": decision_source,
        "label": int(1 if is_accepted else 0),
        "status": "ACCEPTED" if is_accepted else "REJECTED",
        "y": float(suggestion.y),
        "x": float(suggestion.x),
        "score": float(suggestion.score),
        "suggestion_id": str(getattr(suggestion, "suggestion_id", "")),
        "is_gt_match": bool(is_match),
        "distance_to_gt": float(distance),
        "has_suggestion_features": True,
    }

    for idx, name in enumerate(FEATURE_NAMES):
        row[f"fv_{name}"] = float(feature_vector_from_suggestion(suggestion)[idx])

    components = dict(getattr(suggestion, "score_components", {}) or {})
    for key, value in components.items():
        if isinstance(value, (int, float, np.floating)):
            row[f"comp_{key}"] = float(value)

    return row

def decision_row_from_manual_point(
    *,
    iteration: int,
    decision_id: int,
    point: Tuple[float, float],
    gt_points: List[Dict],
    all_suggestions: List,
) -> Dict:
    """Run the decision row from manual point workflow."""
    y, x = float(point[0]), float(point[1])
    is_match, distance = find_nearest_gt((y, x), gt_points)
    row = {
        "decision_id": decision_id,
        "iteration": iteration,
        "decision_source": "manual_outside",
        "label": 1,
        "status": "ACCEPTED",
        "y": y,
        "x": x,
        "score": float("nan"),
        "suggestion_id": "",
        "is_gt_match": bool(is_match),
        "distance_to_gt": float(distance),
        "has_suggestion_features": False,
    }

    nearest = nearest_suggestion_for_features((y, x), all_suggestions)
    if nearest is not None:
        row["has_suggestion_features"] = True
        row["borrowed_feature_suggestion_id"] = str(getattr(nearest, "suggestion_id", ""))
        fv = feature_vector_from_suggestion(nearest)
        for idx, name in enumerate(FEATURE_NAMES):
            row[f"fv_{name}"] = float(fv[idx])
        components = dict(getattr(nearest, "score_components", {}) or {})
        for key, value in components.items():
            if isinstance(value, (int, float, np.floating)):
                row[f"comp_{key}"] = float(value)
    return row

def show_statistics(session: InteractiveSession, gt_points: List[Dict], matched_gt: int):
    """Show statistics for the current workflow."""
    reviewed = max(1, session.processed)
    print("\n" + "─" * 80)
    print("SESSION STATISTICS")
    print("─" * 80)
    print(f"  Total suggestions generated: {session.total_suggestions}")
    print(f"  Decisions processed: {session.processed}")
    print(f"  Accepted: {session.accepted} ({100*session.accepted/reviewed:.1f}%)")
    print(f"  Rejected: {session.rejected} ({100*session.rejected/reviewed:.1f}%)")
    print(f"  Manual accepted outside suggestions: {session.manual_accepted}")
    print(f"  Matched GT points so far: {matched_gt}/{len(gt_points)}")
    print(f"  Retrains so far: {session.retrain_events}")
    if session.retrain_events > 0:
        avg_ms = 1000.0 * session.total_retrain_seconds / session.retrain_events
        print(f"  Avg retrain time: {avg_ms:.2f} ms")
    print("─" * 80 + "\n")

def export_tables(session: InteractiveSession, output_prefix: Path) -> Tuple[Path, Path]:
    """Export tables for the current workflow."""
    decisions_csv = output_prefix.with_name(output_prefix.name + "_decisions.csv")
    annotations_csv = output_prefix.with_name(output_prefix.name + "_accepted_annotations.csv")

    # Decision table with union of all columns.
    all_keys = set()
    for row in session.decision_rows:
        all_keys.update(row.keys())
    ordered = [
        "decision_id",
        "iteration",
        "decision_source",
        "label",
        "status",
        "y",
        "x",
        "score",
        "suggestion_id",
        "borrowed_feature_suggestion_id",
        "is_gt_match",
        "distance_to_gt",
        "has_suggestion_features",
    ]
    remaining = sorted(k for k in all_keys if k not in ordered)
    fieldnames = ordered + remaining

    with decisions_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in session.decision_rows:
            writer.writerow(row)

    annotation_fields = ["annotation_id", "iteration", "decision_source", "y", "x", "is_gt_match", "distance_to_gt"]
    with annotations_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=annotation_fields)
        writer.writeheader()
        for idx, row in enumerate(session.accepted_annotations, 1):
            out = dict(row)
            out["annotation_id"] = idx
            writer.writerow(out)

    return decisions_csv, annotations_csv
