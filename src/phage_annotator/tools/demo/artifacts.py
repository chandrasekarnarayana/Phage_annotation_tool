"""Backward-compatible return wrapper for generated demo assets."""

from __future__ import annotations

from pathlib import Path


class DummyImageArtifacts(tuple):
    """Backward-compatible return wrapper for generated demo assets.

    Acts like ``(image_path, annotation_csv_path)`` for unpacking while also
    behaving like the image path for older callers that pass the return value
    directly into loaders.
    """

    def __new__(cls, image_path: Path, annotation_csv_path: Path):
        """Create the object instance before initialization."""
        return super().__new__(cls, (image_path, annotation_csv_path))

    @property
    def image_path(self) -> Path:
        """Return the image path value."""
        return self[0]

    @property
    def annotation_csv_path(self) -> Path:
        """Return the annotation csv path value."""
        return self[1]

    @property
    def name(self) -> str:
        """Return the name value."""
        return self.image_path.name

    def __fspath__(self) -> str:
        """Return the filesystem path representation."""
        return str(self.image_path)

    def __str__(self) -> str:
        """Return the display string representation."""
        return str(self.image_path)

    def __getattr__(self, attr: str):
        """Delegate unknown attribute access to the wrapped value."""
        return getattr(self.image_path, attr)
