"""Comprehensive test of the Assist feature with demo images.
Tests suggestion generation vs ground truth annotations from demo CSV files.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from scripts.assist_feature_benchmark_split1 import TestMetrics, load_ground_truth, euclidean_distance, match_suggestions_to_ground_truth, test_suggestions_on_image
from scripts.assist_feature_benchmark_split2 import main

if __name__ == "__main__":
    raise SystemExit(main())
