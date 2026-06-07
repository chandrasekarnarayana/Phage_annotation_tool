"""Split definitions from test_critical_logic.py."""


import numpy as np
from phage_annotator.algorithms.analysis import roi_mask_for_polygon, roi_mask_for_shape, roi_mask_from_points
from phage_annotator.cache.projection_cache import ProjectionCache


class TestStaleResultGuard:
    """Test stale result guard to prevent concurrency issues.
    
    Ensures that callback results from cancelled/superseded background jobs
    are not applied, preventing visual corruption in multi-threaded updates.
    """

    def test_gen_job_id_uniqueness(self):
        """Test that generated job IDs are unique."""
        from phage_annotator.framework.stale_result_guard import gen_job_id

        id1 = gen_job_id()
        id2 = gen_job_id()

        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0

    def test_store_and_check_current_job(self):
        """Test storing and checking the current job ID."""
        from phage_annotator.framework.stale_result_guard import (
            gen_job_id,
            store_current_job_id,
            is_current_job,
        )

        job_id = gen_job_id()
        store_current_job_id("projection", job_id)

        # Same job ID should be current
        assert is_current_job("projection", job_id)

    def test_stale_job_rejection(self):
        """Test that old job IDs are rejected as stale."""
        from phage_annotator.framework.stale_result_guard import (
            gen_job_id,
            store_current_job_id,
            is_current_job,
        )

        old_job_id = gen_job_id()
        new_job_id = gen_job_id()

        # Store old job
        store_current_job_id("compute", old_job_id)
        assert is_current_job("compute", old_job_id)

        # Update to new job
        store_current_job_id("compute", new_job_id)

        # Old job should now be stale
        assert not is_current_job("compute", old_job_id)
        # New job should be current
        assert is_current_job("compute", new_job_id)

    def test_different_job_types_independent(self):
        """Test that different job types have independent tracking."""
        from phage_annotator.framework.stale_result_guard import (
            gen_job_id,
            store_current_job_id,
            is_current_job,
        )

        proj_id = gen_job_id()
        load_id = gen_job_id()

        store_current_job_id("projection", proj_id)
        store_current_job_id("load_image", load_id)

        # Each job type tracks independently
        assert is_current_job("projection", proj_id)
        assert is_current_job("load_image", load_id)
        
        # Update projection job
        new_proj_id = gen_job_id()
        store_current_job_id("projection", new_proj_id)

        # Load job should be unaffected
        assert is_current_job("load_image", load_id)
        assert not is_current_job("projection", proj_id)

    def test_clear_job_id(self):
        """Test that job IDs can be cleared."""
        from phage_annotator.framework.stale_result_guard import (
            gen_job_id,
            store_current_job_id,
            is_current_job,
            clear_job_id,
        )

        job_id = gen_job_id()
        store_current_job_id("render", job_id)
        
        assert is_current_job("render", job_id)
        
        # Clear the job ID
        clear_job_id("render")
        
        # Now it should not be current
        assert not is_current_job("render", job_id)

    def test_callback_pattern_safety(self):
        """Test the callback pattern to discard stale results."""
        from phage_annotator.framework.stale_result_guard import (
            gen_job_id,
            store_current_job_id,
            is_current_job,
        )

        # Simulate user triggering job1
        job1 = gen_job_id()
        store_current_job_id("analyze", job1)
        result1_ready = True

        # User quickly triggers job2 before job1 completes
        job2 = gen_job_id()
        store_current_job_id("analyze", job2)

        # When job1 result arrives, callback checks if it's stale
        def process_result(job_id, value):
            """Run the process result workflow."""
            if not is_current_job("analyze", job_id):
                return None  # Discard stale result
            return value * 2

        # Job1 result arrives but is now stale
        result1 = process_result(job1, 42)
        assert result1 is None, "Stale result should be discarded"

        # Job2 result arrives and is current
        result2 = process_result(job2, 21)
        assert result2 == 42, "Current result should be processed"
