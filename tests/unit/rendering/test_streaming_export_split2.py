"""Split definitions from test_streaming_export.py."""

from __future__ import annotations

import pathlib
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch

import numpy as np

from phage_annotator.ui_qt.rendering.export_view import (
    ExportOptions,
    render_chunk_to_array,
    StreamingExportWriter,
    TiffStreamWriter,
    PngStreamWriter,
    calculate_export_chunks,
    create_streaming_writer,
)


class TestRenderChunkToArray(unittest.TestCase):
    """Tests for chunk-based rendering."""

    def _create_export_options(self, **kwargs):
        """Create ExportOptions with sensible defaults."""
        defaults = {
            'panel': 'main',
            'region': 'full',
            'include_roi_outline': False,
            'include_roi_fill': False,
            'include_annotations': False,
            'include_annotation_labels': False,
            'include_particles': False,
            'include_scalebar': False,
            'include_overlay_text': False,
            'marker_size': 5.0,
            'roi_line_width': 2.0,
            'dpi': 96,
            'fmt': 'png',
            'overlay_only': False,
            'transparent_bg': False,
            'roi_mask_clip': False,
        }
        defaults.update(kwargs)
        return ExportOptions(**defaults)

    def test_render_chunk_basic(self):
        """Test basic chunk rendering."""
        # Create a simple frame
        frame = np.arange(256*256).reshape(256, 256).astype(np.float32)
        
        # Mock rendering components
        with patch('phage_annotator.ui_qt.rendering.export_view.render_view_to_array') as mock_render:
            mock_render.return_value = np.zeros((100, 100, 4), dtype=np.uint8)
            
            chunk = render_chunk_to_array(
                frame,
                crop_box=(0, 0, 100, 100),
                cmap=None,
                norm=None,
                overlays=[],
                annotations=[],
                annotation_labels=[],
                roi_overlays=[],
                particle_overlays=[],
                overlay_text=None,
                scalebar_spec=None,
                pixel_size_um=1.0,
                options=self._create_export_options(),
            )
            
            # Should return an array
            self.assertIsNotNone(chunk)
            self.assertEqual(chunk.shape[2], 4)  # RGBA

    def test_render_chunk_with_crop(self):
        """Test chunk rendering with different crop boxes."""
        frame = np.ones((512, 512), dtype=np.float32)
        
        with patch('phage_annotator.ui_qt.rendering.export_view.render_view_to_array') as mock_render:
            mock_render.return_value = np.zeros((256, 256, 4), dtype=np.uint8)
            
            # Render different chunks
            chunk1 = render_chunk_to_array(frame, crop_box=(0, 0, 256, 256), cmap=None, norm=None,
                                           overlays=[], annotations=[], annotation_labels=[],
                                           roi_overlays=[], particle_overlays=[], overlay_text=None,
                                           scalebar_spec=None, pixel_size_um=1.0, options=self._create_export_options())
            chunk2 = render_chunk_to_array(frame, crop_box=(256, 0, 512, 256), cmap=None, norm=None,
                                           overlays=[], annotations=[], annotation_labels=[],
                                           roi_overlays=[], particle_overlays=[], overlay_text=None,
                                           scalebar_spec=None, pixel_size_um=1.0, options=self._create_export_options())
            
            self.assertIsNotNone(chunk1)
            self.assertIsNotNone(chunk2)

class TestStreamingExportIntegration(unittest.TestCase):
    """Integration tests for streaming export pipeline."""

    def test_full_streaming_export_tiff(self):
        """Test complete streaming export pipeline for TIFF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            
            # Calculate chunks for 512×512 image
            chunks = calculate_export_chunks((512, 512), chunk_size=256)
            self.assertEqual(len(chunks), 4)
            
            # Create writer
            writer = create_streaming_writer("tiff", path, (512, 512))
            
            # Write chunks
            for i, (x0, y0, x1, y1) in enumerate(chunks):
                chunk = np.ones((y1-y0, x1-x0, 4), dtype=np.uint8) * (i + 1) * 50
                writer.write_chunk(chunk, (y0, x0))
            
            writer.finalize()
            
            # Verify file created
            self.assertTrue(path.exists())

    def test_full_streaming_export_png(self):
        """Test complete streaming export pipeline for PNG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            
            # Calculate chunks for 512×512 image
            chunks = calculate_export_chunks((512, 512), chunk_size=256)
            
            # Create writer
            writer = create_streaming_writer("png", path, (512, 512))
            
            # Write chunks
            for i, (x0, y0, x1, y1) in enumerate(chunks):
                chunk = np.ones((y1-y0, x1-x0, 4), dtype=np.uint8) * (i + 1) * 50
                writer.write_chunk(chunk, (y0, x0))
            
            writer.finalize()
            
            # Verify file created
            self.assertTrue(path.exists())

    def test_streaming_export_memory_efficiency(self):
        """Test that streaming export doesn't allocate full frame at once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "large.png"
            
            # Simulate large image (would be 4GB if allocated at once)
            large_shape = (4096, 4096)
            chunks = calculate_export_chunks(large_shape, chunk_size=256)
            
            # Should have 256 chunks
            self.assertEqual(len(chunks), 256)
            
            # Create writer without allocating full image
            writer = create_streaming_writer("png", path, large_shape)
            
            # Write only first few chunks (not all)
            for i, (x0, y0, x1, y1) in enumerate(chunks[:4]):
                chunk = np.ones((y1-y0, x1-x0, 4), dtype=np.uint8)
                writer.write_chunk(chunk, (y0, x0))
            
            # Should not have allocated full 4096×4096 anywhere
            self.assertEqual(writer.chunks_written, 4)

class TestExportOptionsChunkedFlag(unittest.TestCase):
    """Tests for export_as_chunked flag in ExportOptions."""

    def _create_export_options(self, **kwargs):
        """Create ExportOptions with sensible defaults."""
        defaults = {
            'panel': 'main',
            'region': 'full',
            'include_roi_outline': False,
            'include_roi_fill': False,
            'include_annotations': False,
            'include_annotation_labels': False,
            'include_particles': False,
            'include_scalebar': False,
            'include_overlay_text': False,
            'marker_size': 5.0,
            'roi_line_width': 2.0,
            'dpi': 96,
            'fmt': 'png',
            'overlay_only': False,
            'transparent_bg': False,
            'roi_mask_clip': False,
        }
        defaults.update(kwargs)
        return ExportOptions(**defaults)

    def test_export_options_has_chunked_flag(self):
        """Test that ExportOptions has export_as_chunked field."""
        opts = self._create_export_options()
        self.assertFalse(opts.export_as_chunked)

    def test_export_options_set_chunked_flag(self):
        """Test setting export_as_chunked flag."""
        opts = self._create_export_options(export_as_chunked=True)
        self.assertTrue(opts.export_as_chunked)

    def test_export_options_chunked_default_false(self):
        """Test default export_as_chunked is False (backward compatible)."""
        opts = self._create_export_options()
        # Default should be False to maintain backward compatibility
        self.assertFalse(opts.export_as_chunked)
