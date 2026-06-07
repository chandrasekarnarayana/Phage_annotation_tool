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


from scripts.assist_interactive_cli_split2 import interactive_test_image

def main():
    """Run the main workflow."""
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
