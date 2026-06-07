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


from scripts.assist_interactive_cli_split1 import InteractiveSession, load_ground_truth, find_nearest_gt, greedy_match_count, parse_manual_points, decision_row_from_suggestion, decision_row_from_manual_point, show_statistics, export_tables

def interactive_test_image(
    image_path: Path,
    csv_path: Path,
    *,
    batch_size: int = 10,
    retrain_every: int = 10,
    max_iterations: int = 0,
):
    """Run the interactive test image workflow."""
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
