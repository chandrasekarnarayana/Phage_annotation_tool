"""LOD-first rendering and pyramid prefetch tests.

LOD-first rendering:
- When full-res projection is missing, return 8x pyramid level as fallback
- Mark image as being in LOD mode while full-res loads
- Automatically transition to full-res when available

Pyramid prefetch:
- Schedule pyramid jobs (8x, 4x, 2x) alongside full-res
- Ensures LOD preview is available faster than full-res computation

Tests moved into sibling split modules to keep file size below 300 lines.
"""
