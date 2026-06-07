"""Tests for modality configuration persistence.

This module validates:
- Saving modality_manager to .phageproj files
- Loading modality_manager from .phageproj files
- Backward compatibility (projects without modality_manager)
- Schema versioning

Tests moved into sibling split modules to keep file size below 300 lines.
"""
