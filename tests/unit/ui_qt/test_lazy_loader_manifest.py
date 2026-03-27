"""Unit coverage for the lazy loader manifest model."""

from __future__ import annotations

from pathlib import Path

from phage_annotator.ui_qt.models.lazy_loader import (
    LAZY_TABLE_HEADERS,
    LazyLoaderManifest,
    LazyTableRowSpec,
    normalize_lazy_sync_groups,
)


def test_manifest_tracks_folder_contents_and_undo(tmp_path) -> None:
    """Folders should expose child files and support undo of removals."""
    folder = tmp_path / "dataset"
    folder.mkdir()
    nested = folder / "nested"
    nested.mkdir()
    image_a = folder / "a.tif"
    image_b = nested / "b.tiff"
    image_a.write_bytes(b"fake")
    image_b.write_bytes(b"fake")

    manifest = LazyLoaderManifest()
    manifest.add_paths([folder], {str(image_a): [0], str(image_b): [1]})

    frame = manifest.to_frame()
    assert list(frame["name"]) == ["dataset", "nested", "b.tiff", "a.tif"]
    assert manifest.visible_image_ids() == [1, 0]

    assert manifest.remove_path(str(image_a))
    assert str(image_a) not in set(manifest.to_frame()["path"])

    restored = manifest.undo_last_removal()
    assert restored == str(image_a)
    assert str(image_a) in set(manifest.to_frame()["path"])


def test_normalize_lazy_sync_groups_defaults_by_source_image() -> None:
    """Rows from the same source image should default to the same sync group."""
    rows = [
        LazyTableRowSpec(
            role_key=0,
            panel_key="frame",
            panel_name="Frame",
            source_image_id=10,
            projection_key="raw",
            group_key="",
            visible=True,
            show_points=True,
            sync_contrast=True,
            sync_view=True,
            sync_time=True,
        ),
        LazyTableRowSpec(
            role_key="builtin:mean",
            panel_key="mean",
            panel_name="Mean",
            source_image_id=10,
            projection_key="mean",
            group_key="",
            visible=True,
            show_points=True,
            sync_contrast=True,
            sync_view=True,
            sync_time=True,
        ),
        LazyTableRowSpec(
            role_key=1,
            panel_key="support",
            panel_name="Support",
            source_image_id=11,
            projection_key="raw",
            group_key="",
            visible=True,
            show_points=True,
            sync_contrast=True,
            sync_view=True,
            sync_time=True,
        ),
    ]

    groups = normalize_lazy_sync_groups(rows, {})

    assert groups[0] == groups["builtin:mean"]
    assert groups[1] != groups[0]


def test_normalize_lazy_sync_groups_preserves_existing_numeric_assignments() -> None:
    """Existing numeric user assignments should be preserved during normalization."""
    rows = [
        LazyTableRowSpec(
            role_key=0,
            panel_key="frame",
            panel_name="Frame",
            source_image_id=10,
            projection_key="raw",
            group_key="7",
            visible=True,
            show_points=True,
            sync_contrast=True,
            sync_view=True,
            sync_time=True,
        ),
        LazyTableRowSpec(
            role_key="builtin:mean",
            panel_key="mean",
            panel_name="Mean",
            source_image_id=10,
            projection_key="mean",
            group_key="",
            visible=True,
            show_points=True,
            sync_contrast=True,
            sync_view=True,
            sync_time=True,
        ),
    ]

    groups = normalize_lazy_sync_groups(rows, {0: "7"})

    assert groups[0] == "7"
    assert groups["builtin:mean"] == "7"


def test_lazy_table_sync_headers_are_explicit() -> None:
    """Sync headers should use explicit scientific wording."""
    assert LAZY_TABLE_HEADERS[8:] == ("Contrast", "Zoom/Pan", "Playback")
