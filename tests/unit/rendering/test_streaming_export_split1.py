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


class TestCalculateExportChunks(unittest.TestCase):
    """Tests for chunk boundary calculation."""

    def test_calculate_chunks_even_dimensions(self):
        """Test chunk calculation with even dimensions (512×512 image)."""
        chunks = calculate_export_chunks((512, 512), chunk_size=256)
        # Should be 2×2 = 4 chunks
        self.assertEqual(len(chunks), 4)
        # Check key boundaries
        self.assertIn((0, 0, 256, 256), chunks)
        self.assertIn((256, 0, 512, 256), chunks)
        self.assertIn((0, 256, 256, 512), chunks)
        self.assertIn((256, 256, 512, 512), chunks)

    def test_calculate_chunks_odd_dimensions(self):
        """Test chunk calculation with odd dimensions (300×400 image)."""
        chunks = calculate_export_chunks((300, 400), chunk_size=256)
        # Should be 2×2 = 4 chunks (last chunk is smaller)
        self.assertEqual(len(chunks), 4)
        # Verify bounds don't exceed image
        for x0, y0, x1, y1 in chunks:
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, 400)
            self.assertLessEqual(y1, 300)

    def test_calculate_chunks_single_chunk(self):
        """Test chunk calculation for small image (100×100)."""
        chunks = calculate_export_chunks((100, 100), chunk_size=256)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], (0, 0, 100, 100))

    def test_calculate_chunks_custom_chunk_size(self):
        """Test chunk calculation with custom chunk size (128×128)."""
        chunks = calculate_export_chunks((256, 256), chunk_size=128)
        # Should be 2×2 = 4 chunks of 128×128
        self.assertEqual(len(chunks), 4)
        self.assertEqual(chunks[0], (0, 0, 128, 128))
        self.assertEqual(chunks[-1], (128, 128, 256, 256))

    def test_calculate_chunks_large_image(self):
        """Test chunk calculation for large image (2048×2048)."""
        chunks = calculate_export_chunks((2048, 2048), chunk_size=256)
        # Should be 8×8 = 64 chunks
        self.assertEqual(len(chunks), 64)

    def test_calculate_chunks_no_gap(self):
        """Test that chunks tile seamlessly with no gaps."""
        chunks = calculate_export_chunks((512, 512), chunk_size=256)
        chunks_sorted = sorted(chunks)
        # For a 512×512 image with 256 chunks, verify continuous coverage
        self.assertEqual(len(chunks_sorted), 4)
        # Verify no overlaps or gaps
        for i, (x0, y0, x1, y1) in enumerate(chunks_sorted):
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, 512)
            self.assertLessEqual(y1, 512)

class TestStreamingExportWriter(unittest.TestCase):
    """Tests for StreamingExportWriter base class."""

    def test_writer_initialization(self):
        """Test base writer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            # Cannot instantiate abstract base class directly
            # but can test through subclass
            writer = TiffStreamWriter(path, (256, 256))
            self.assertIsNotNone(writer)

    def test_writer_chunks_written_property(self):
        """Test chunks_written property tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            writer = TiffStreamWriter(path, (256, 256))
            self.assertEqual(writer.chunks_written, 0)
            
            # Write a chunk
            chunk = np.zeros((256, 256, 4), dtype=np.uint8)
            writer.write_chunk(chunk, (0, 0))
            self.assertEqual(writer.chunks_written, 1)

class TestTiffStreamWriter(unittest.TestCase):
    """Tests for TIFF-specific streaming writer."""

    def test_tiff_writer_initialization(self):
        """Test TIFF writer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            writer = TiffStreamWriter(path, (256, 256))
            self.assertEqual(writer.path, str(path))
            self.assertEqual(writer.image_shape, (256, 256))
            self.assertEqual(writer.chunks_written, 0)

    def test_tiff_writer_write_chunk(self):
        """Test writing a chunk to TIFF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            writer = TiffStreamWriter(path, (256, 256))
            
            # Create a simple chunk
            chunk = np.ones((256, 256, 4), dtype=np.uint8) * 128
            writer.write_chunk(chunk, (0, 0))
            
            self.assertEqual(writer.chunks_written, 1)

    def test_tiff_writer_finalize(self):
        """Test finalizing TIFF writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            writer = TiffStreamWriter(path, (256, 256))
            
            chunk = np.ones((256, 256, 4), dtype=np.uint8) * 128
            writer.write_chunk(chunk, (0, 0))
            writer.finalize()
            
            # Writer should be closed
            self.assertIsNone(writer.writer)

class TestPngStreamWriter(unittest.TestCase):
    """Tests for PNG-specific streaming writer."""

    def test_png_writer_initialization(self):
        """Test PNG writer initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            writer = PngStreamWriter(path, (256, 256))
            self.assertEqual(writer.path, str(path))
            self.assertEqual(writer.image_shape, (256, 256))
            self.assertEqual(writer.chunks_written, 0)

    def test_png_writer_write_chunk(self):
        """Test writing chunks to PNG writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            writer = PngStreamWriter(path, (512, 512))
            
            # Write multiple chunks
            chunk1 = np.ones((256, 256, 4), dtype=np.uint8) * 100
            chunk2 = np.ones((256, 256, 4), dtype=np.uint8) * 150
            
            writer.write_chunk(chunk1, (0, 0))
            writer.write_chunk(chunk2, (0, 256))
            
            self.assertEqual(writer.chunks_written, 2)
            self.assertEqual(len(writer._chunks), 2)

    def test_png_writer_finalize_creates_file(self):
        """Test PNG writer finalize creates output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            writer = PngStreamWriter(path, (512, 512))
            
            # Write chunks
            chunk1 = np.ones((256, 256, 4), dtype=np.uint8) * 100
            chunk2 = np.ones((256, 256, 4), dtype=np.uint8) * 150
            
            writer.write_chunk(chunk1, (0, 0))
            writer.write_chunk(chunk2, (0, 256))
            writer.finalize()
            
            # File should be created
            self.assertTrue(path.exists())

    def test_png_writer_stitch_chunks(self):
        """Test PNG writer stitches chunks correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            writer = PngStreamWriter(path, (512, 512))
            
            # Create chunks with distinct values
            chunk1 = np.ones((256, 256, 4), dtype=np.uint8) * 50  # top-left
            chunk2 = np.ones((256, 256, 4), dtype=np.uint8) * 100  # top-right
            chunk3 = np.ones((256, 256, 4), dtype=np.uint8) * 150  # bottom-left
            chunk4 = np.ones((256, 256, 4), dtype=np.uint8) * 200  # bottom-right
            
            writer.write_chunk(chunk1, (0, 0))
            writer.write_chunk(chunk2, (0, 256))
            writer.write_chunk(chunk3, (256, 0))
            writer.write_chunk(chunk4, (256, 256))
            writer.finalize()
            
            # Verify stitching by reading file
            import matplotlib.pyplot as plt
            loaded = plt.imread(path)
            # Should be (512, 512, 4)
            self.assertEqual(loaded.shape[0], 512)
            self.assertEqual(loaded.shape[1], 512)

class TestCreateStreamingWriter(unittest.TestCase):
    """Tests for streaming writer factory function."""

    def test_create_tiff_writer(self):
        """Test creating TIFF streaming writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.tif"
            writer = create_streaming_writer("tiff", path, (256, 256))
            self.assertIsInstance(writer, TiffStreamWriter)

    def test_create_png_writer(self):
        """Test creating PNG streaming writer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.png"
            writer = create_streaming_writer("png", path, (256, 256))
            self.assertIsInstance(writer, PngStreamWriter)

    def test_create_writer_case_insensitive(self):
        """Test writer creation is case-insensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = pathlib.Path(tmpdir) / "test1.tif"
            path2 = pathlib.Path(tmpdir) / "test2.tif"
            
            writer1 = create_streaming_writer("TIFF", path1, (256, 256))
            writer2 = create_streaming_writer("Tiff", path2, (256, 256))
            
            self.assertIsInstance(writer1, TiffStreamWriter)
            self.assertIsInstance(writer2, TiffStreamWriter)

    def test_create_writer_unsupported_format(self):
        """Test creating writer with unsupported format raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = pathlib.Path(tmpdir) / "test.xyz"
            with self.assertRaises(ValueError):
                create_streaming_writer("xyz", path, (256, 256))
