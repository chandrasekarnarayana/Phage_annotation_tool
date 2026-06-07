"""Interactive iterative testing for assist suggestions.

Enhancements in this version:
  1. Decisions are counted globally; retraining triggers every N decisions (default 10).
  2. Manual accepted points outside shown suggestions can be entered and counted.
  3. Decision table is exported with accept/reject labels and full feature columns.
  4. Accepted annotations are exported as an annotation table.
  5. Retraining duration is measured and reported.

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from scripts.assist_interactive_cli_split1 import InteractiveSession, load_ground_truth, euclidean_distance, find_nearest_gt, greedy_match_count, parse_manual_points, nearest_suggestion_for_features, decision_row_from_suggestion, decision_row_from_manual_point, show_statistics, export_tables
from scripts.assist_interactive_cli_split2 import interactive_test_image
from scripts.assist_interactive_cli_split3 import main

if __name__ == "__main__":
    raise SystemExit(main())
