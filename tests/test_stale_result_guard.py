"""Unit tests for stale-result guard module."""

from phage_annotator.stale_result_guard import (clear_job_id, gen_job_id, is_current_job,
                                                store_current_job_id)


class TestStaleResultGuard:
    """Test stale-result protection for background jobs."""

    def test_gen_job_id_uniqueness(self):
        """Test that generated job IDs are unique."""
        id1 = gen_job_id()
        id2 = gen_job_id()
        assert id1 != id2
        assert isinstance(id1, str)
        assert isinstance(id2, str)

    def test_store_and_check_current_job(self):
        """Test storing and checking current job."""
        job_type = "test_job"
        job_id = gen_job_id()

        # Initially no job is current
        assert not is_current_job(job_type, job_id)

        # Store it
        store_current_job_id(job_type, job_id)
        assert is_current_job(job_type, job_id)

    def test_new_job_supersedes_old(self):
        """Test that new job IDs supersede old ones."""
        job_type = "render_job"
        old_id = gen_job_id()
        new_id = gen_job_id()

        store_current_job_id(job_type, old_id)
        assert is_current_job(job_type, old_id)
        assert not is_current_job(job_type, new_id)

        # New job becomes current
        store_current_job_id(job_type, new_id)
        assert not is_current_job(job_type, old_id)
        assert is_current_job(job_type, new_id)

    def test_clear_job_id(self):
        """Test clearing job ID."""
        job_type = "load_job"
        job_id = gen_job_id()

        store_current_job_id(job_type, job_id)
        assert is_current_job(job_type, job_id)

        clear_job_id(job_type)
        assert not is_current_job(job_type, job_id)

    def test_independent_job_types(self):
        """Test that different job types maintain separate IDs."""
        job1_type = "job_type_1"
        job2_type = "job_type_2"
        job1_id = gen_job_id()
        job2_id = gen_job_id()

        store_current_job_id(job1_type, job1_id)
        store_current_job_id(job2_type, job2_id)

        assert is_current_job(job1_type, job1_id)
        assert is_current_job(job2_type, job2_id)
        assert not is_current_job(job1_type, job2_id)
        assert not is_current_job(job2_type, job1_id)

    def test_callback_pattern(self):
        """Test the documented callback pattern."""
        job_type = "compute_projection"

        # Simulate first job
        job_id_1 = gen_job_id()
        store_current_job_id(job_type, job_id_1)

        # Simulate result callback for first job
        def on_result_1(job_id, value):
            if not is_current_job(job_type, job_id):
                return False  # Stale result
            return True  # Process it

        assert on_result_1(job_id_1, "data1") is True

        # Simulate second job (supersedes first)
        job_id_2 = gen_job_id()
        store_current_job_id(job_type, job_id_2)

        # First job's callback should now reject results
        assert on_result_1(job_id_1, "data1") is False

        # Second job's callback should accept results
        def on_result_2(job_id, value):
            if not is_current_job(job_type, job_id):
                return False  # Stale result
            return True  # Process it

        assert on_result_2(job_id_2, "data2") is True
