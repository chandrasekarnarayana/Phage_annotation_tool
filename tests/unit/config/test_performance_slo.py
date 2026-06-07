"""Unit tests for configured performance service-level objectives."""

from phage_annotator.config.performance import DEFAULT_SLO, REFERENCE_DATASET


def test_default_slo_values_present() -> None:
    """Verify default slo values present for the current workflow."""
    assert DEFAULT_SLO.frame_step_p50_ms > 0
    assert DEFAULT_SLO.frame_step_p95_ms >= DEFAULT_SLO.frame_step_p50_ms
    assert DEFAULT_SLO.z_step_p50_ms > 0
    assert DEFAULT_SLO.redraw_p95_ms >= DEFAULT_SLO.redraw_p50_ms


def test_reference_dataset_shape() -> None:
    """Verify reference dataset shape for the current workflow."""
    shape = REFERENCE_DATASET.get("shape")
    assert isinstance(shape, tuple)
    assert len(shape) == 4
