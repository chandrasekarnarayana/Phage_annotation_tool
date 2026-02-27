"""Backward compatibility facade for project I/O helpers.

This module has been moved to phage_annotator.io.projects.base.
"""

from phage_annotator.io.projects.base import load_project, save_project

__all__ = ["load_project", "save_project"]
