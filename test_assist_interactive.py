#!/usr/bin/env python3
"""Interactive iterative testing for assist suggestions.

Enhancements in this version:
  1. Decisions are counted globally; retraining triggers every N decisions (default 10).
  2. Manual accepted points outside shown suggestions can be entered and counted.
  3. Decision table is exported with accept/reject labels and full feature columns.
  4. Accepted annotations are exported as an annotation table.
  5. Retraining duration is measured and reported.
"""

from __future__ import annotations

import csv
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from tifffile import imread

sys.path.insert(0, str(Path(__file__).parent / "src"))

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
    return float(np.hypot(p1[0] - p2[0], p1[1] - p2[1]))


def find_nearest_gt(
    suggestion_pos: Tuple[float, float], gt_points: List[Dict], distance_threshold: float = 5.0
) -> Tuple[bool, float]:
    if not gt_points:
        return False, float("inf")
    distances = [euclidean_distance(suggestion_pos, (g["y"], g["x"])) for g in gt_points]
    min_dist = min(distances)
    return min_dist <= distance_threshold, min_dist


def greedy_match_count(points: List[Tuple[float, float]], gt_points: List[Dict], threshold: float = 5.0) -> int:
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


def interactive_test_image(
    image_path: Path,
    csv_path: Path,
    *,
    batch_size: int = 10,
    retrain_every: int = 10,
    max_iterations: int = 0,
):
    print("\n" + "█" * 80)
    print(f"█ INTERACTIVE ASSIST FEATURE TEST: {image_path.name}".ljust(79) + "█")
    print("█" * 80)

    image_data = imread(str(image_path))
    ground_truth = load_ground_truth(csv_path)
    t_idx = max(ground_truth.keys(), key=lambda t: len(ground_truth[t]))
    gt_points = ground_truth[t_idx]

    if image_data.ndim == 4:
        slice_2d = image_data[t_idx, 0, :, :]
    elif image_data.ndim == 3:
        slice_2d = image_data[t_idx, :, :]
    else:
        slice_2d = image_data

    print(f"\nImage shape: {image_data.shape}")
    print(f"Testing timepoint: {t_idx} ({len(gt_points)} GT points)")

    model = LocalPeakSuggestionModel(min_distance_px=6, threshold_quantile=0.995, max_points=None)
    predict_start = time.perf_counter()
    all_suggestions = model.predict(
        slice_2d,
        image_id=1,
        image_name=str(image_path.name),
        t=t_idx,
        z=0,
        label="phage",
        strategy="raw",
    )
    predict_seconds = time.perf_counter() - predict_start

    all_suggestions = sorted(all_suggestions, key=lambda s: float(s.score), reverse=True)
    session = InteractiveSession(image_name=image_path.name, total_suggestions=len(all_suggestions))
    ranker = LightweightSuggestionRanker()

    remaining = list(all_suggestions)
    decisions_since_retrain = 0
    decision_id = 0
    iteration = 1

    print(f"Generated {len(all_suggestions)} suggestions in {predict_seconds:.3f}s")
    print(f"Retrain trigger: every {retrain_every} decisions (suggested + manual)")

    while remaining:
        if max_iterations > 0 and iteration > max_iterations:
            break

        print(f"\n{'╔' + '═'*78 + '╗'}")
        print(f"║ ITERATION {iteration}: Review up to {batch_size} suggestions (remaining: {len(remaining)})".ljust(79) + "║")
        print(f"╚{'═'*78 + '╝'}")

        batch = remaining[:batch_size]
        reviewed_count = 0

        for i, suggestion in enumerate(batch, 1):
            y, x, score = float(suggestion.y), float(suggestion.x), float(suggestion.score)
            is_match, distance = find_nearest_gt((y, x), gt_points)
            marker = "✅" if is_match else "❌"
            print(f"[{i:2d}] {marker} score={score:.3f} pos=({y:7.1f},{x:7.1f}) gt_dist={distance:.1f}px")

            while True:
                answer = input("      accept/reject/skip [y/n/s]: ").strip().lower()
                if answer in {"", "y", "yes"}:
                    accepted = True
                    break
                if answer in {"n", "no"}:
                    accepted = False
                    break
                if answer in {"s", "skip"}:
                    accepted = None
                    break
                print("      invalid input, use y/n/s")

            if accepted is None:
                continue

            decision_id += 1
            reviewed_count += 1
            session.processed += 1
            decisions_since_retrain += 1
            if accepted:
                session.accepted += 1
                session.accepted_annotations.append(
                    {
                        "iteration": iteration,
                        "decision_source": "suggestion",
                        "y": y,
                        "x": x,
                        "is_gt_match": is_match,
                        "distance_to_gt": float(distance),
                    }
                )
            else:
                session.rejected += 1

            session.decision_rows.append(
                decision_row_from_suggestion(
                    iteration=iteration,
                    decision_id=decision_id,
                    is_accepted=accepted,
                    suggestion=suggestion,
                    decision_source="suggestion",
                    gt_points=gt_points,
                )
            )

        # Remove only displayed suggestions.
        remaining = remaining[batch_size:]

        manual_text = input(
            "Add accepted points outside shown suggestions as y,x; y,x (Enter=none): "
        )
        manual_points = parse_manual_points(manual_text)
        for point in manual_points:
            decision_id += 1
            session.processed += 1
            session.accepted += 1
            session.manual_accepted += 1
            decisions_since_retrain += 1

            row = decision_row_from_manual_point(
                iteration=iteration,
                decision_id=decision_id,
                point=point,
                gt_points=gt_points,
                all_suggestions=all_suggestions,
            )
            session.decision_rows.append(row)
            session.accepted_annotations.append(
                {
                    "iteration": iteration,
                    "decision_source": "manual_outside",
                    "y": float(point[0]),
                    "x": float(point[1]),
                    "is_gt_match": bool(row["is_gt_match"]),
                    "distance_to_gt": float(row["distance_to_gt"]),
                }
            )

        accepted_points = [(float(r["y"]), float(r["x"])) for r in session.accepted_annotations]
        matched_gt = greedy_match_count(accepted_points, gt_points)

        if decisions_since_retrain >= retrain_every:
            train_rows = [r for r in session.decision_rows if bool(r.get("has_suggestion_features", False))]
            if len(train_rows) >= 2 and len(set(int(r["label"]) for r in train_rows)) >= 2:
                x = np.asarray(
                    [[float(r[f"fv_{name}"]) for name in FEATURE_NAMES] for r in train_rows], dtype=np.float64
                )
                y = np.asarray([int(r["label"]) for r in train_rows], dtype=np.float64)
                fit_start = time.perf_counter()
                ranker.fit(x, y)
                fit_seconds = time.perf_counter() - fit_start
                session.retrain_events += 1
                session.total_retrain_seconds += fit_seconds

                remaining = ranker.apply_to_suggestions(remaining)
                remaining = sorted(remaining, key=lambda s: float(s.score), reverse=True)
                print(
                    f"→ Retrained on {len(train_rows)} rows in {1000.0*fit_seconds:.2f} ms; reranked {len(remaining)} remaining suggestions"
                )
            else:
                print("→ Retrain trigger reached, but skipped (need both accepted and rejected feature-bearing rows)")
            decisions_since_retrain = 0

        show_statistics(session, gt_points, matched_gt)

        if matched_gt >= len(gt_points):
            print("✓ Complete annotation reached for this frame (all GT points matched)")
            break

        if remaining:
            cont = input(f"Continue to iteration {iteration + 1}? [y/n]: ").strip().lower()
            if cont not in {"", "y", "yes"}:
                break

        iteration += 1

    prefix = image_path.with_suffix("")
    decisions_csv, annotations_csv = export_tables(session, prefix)

    accepted_points = [(float(r["y"]), float(r["x"])) for r in session.accepted_annotations]
    matched_gt = greedy_match_count(accepted_points, gt_points)
    precision = matched_gt / max(1, len(session.accepted_annotations))
    recall = matched_gt / max(1, len(gt_points))
    completed_iterations = iteration
    estimated_total_iterations = int(np.ceil(len(gt_points) / max(1, batch_size)))

    print("\n" + "█" * 80)
    print(f"█ FINAL SUMMARY".ljust(79) + "█")
    print("█" * 80)
    print(f"Image: {session.image_name}")
    print(f"Timepoint tested: {t_idx}")
    print(f"Ground truth points: {len(gt_points)}")
    print(f"Decisions processed: {session.processed}")
    print(f"Accepted: {session.accepted} (manual outside: {session.manual_accepted})")
    print(f"Rejected: {session.rejected}")
    print(f"GT matches from accepted annotations: {matched_gt}")
    print(f"Precision (accepted vs GT): {precision:.3f}")
    print(f"Recall (accepted coverage): {recall:.3f}")
    print(f"Iterations completed: {completed_iterations}")
    print(f"Estimated iterations for full coverage at {batch_size}/iter: ~{estimated_total_iterations}")
    print(f"Initial prediction time: {predict_seconds:.3f}s")
    print(f"Retrain events: {session.retrain_events}")
    if session.retrain_events > 0:
        print(f"Total retrain time: {session.total_retrain_seconds:.4f}s")
        print(f"Average retrain time: {1000*session.total_retrain_seconds/session.retrain_events:.2f} ms")
    print(f"Decision table exported: {decisions_csv}")
    print(f"Accepted annotation table exported: {annotations_csv}")
    print("█" * 80 + "\n")

    return session


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Interactive assist feature testing")
    parser.add_argument("--image", required=True, help="Path to test image")
    parser.add_argument("--csv", required=True, help="Path to ground truth CSV")
    parser.add_argument("--batch-size", type=int, default=10, help="Suggestions shown per iteration")
    parser.add_argument(
        "--retrain-every",
        type=int,
        default=10,
        help="Trigger retraining every N decisions (includes manual outside points)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Maximum iterations (0 means no hard limit)",
    )
    args = parser.parse_args()

    image_path = Path(args.image)
    csv_path = Path(args.csv)

    if not image_path.exists():
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}")
        sys.exit(1)

    interactive_test_image(
        image_path,
        csv_path,
        batch_size=max(1, int(args.batch_size)),
        retrain_every=max(1, int(args.retrain_every)),
        max_iterations=max(0, int(args.max_iterations)),
    )
    print("✅ Interactive testing complete!")


if __name__ == "__main__":
    main()
