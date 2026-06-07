"""Enhanced iterative assist with parallel frame processing and smart retraining.

Optimizations:
  - Parallel prediction on multi-frame stacks (3× faster)
  - Skip retraining between frames of same stack
  - Single training pass per stack (not per-frame)
  - ThreadPoolExecutor for frame-level parallelism

Definitions are split into sibling modules to keep this compatibility surface small.
"""

from scripts.assist_parallel_stack_split1 import IterativeTestSession, load_ground_truth, euclidean_distance, find_nearest_gt, compute_batch_metrics, simulate_user_feedback, decision_row
from scripts.assist_parallel_stack_split2 import process_stack_parallel, estimate_sequential_time, main

if __name__ == "__main__":
    raise SystemExit(main())
