"""Stale-result protection for background job callbacks.

Ensures that result callbacks only process results from the active job
and discard results from cancelled/superseded jobs. This is a critical
safety layer when multiple jobs of the same type can run in sequence.

Pattern:
    job_id = gen_job_id()
    handle = self.job_manager.submit("job_type", worker_func, args)
    store_current_job_id("job_type", job_id)

Then in the callback:
    def on_result(job_id, value):
        if not is_current_job("job_type", job_id):
            return  # Discard stale result
        # Process value...
"""

from __future__ import annotations

import threading
from typing import Any, Dict

__all__ = [
    "gen_job_id",
    "store_current_job_id",
    "is_current_job",
    "clear_job_id",
]

# Thread-safe tracking of active job IDs by job type
_job_id_lock = threading.Lock()
_active_job_ids: Dict[str, str] = {}


def gen_job_id() -> str:
    """Generate a unique job ID."""
    import uuid

    return str(uuid.uuid4())


def store_current_job_id(job_type: str, job_id: str) -> None:
    """Register the given job ID as the current active job for this type.

    Parameters
    ----------
    job_type : str
        Job type identifier (e.g., "compute_projection", "load_image").
    job_id : str
        Unique job ID to track.
    """
    with _job_id_lock:
        _active_job_ids[job_type] = job_id


def is_current_job(job_type: str, job_id: str) -> bool:
    """Check if the given job ID matches the current active job.

    Use this in result callbacks to discard stale results.

    Parameters
    ----------
    job_type : str
        Job type identifier.
    job_id : str
        Job ID to check.

    Returns
    -------
    bool
        True if this job_id is still the active job for its type.
    """
    with _job_id_lock:
        return _active_job_ids.get(job_type) == job_id


def clear_job_id(job_type: str) -> None:
    """Clear the current active job ID for this type.

    Use when the job is explicitly completed/cancelled.

    Parameters
    ----------
    job_type : str
        Job type identifier.
    """
    with _job_id_lock:
        _active_job_ids.pop(job_type, None)
