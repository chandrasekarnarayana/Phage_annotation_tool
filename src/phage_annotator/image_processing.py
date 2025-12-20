"""Image processing helpers (placeholder for future visualization work)."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from PIL import Image


def _ensure_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Pillow is required for image operations. Install with `pip install pillow`."
        ) from exc
    return Image


def load_image(path: pathlib.Path) -> "Image.Image":
    """Load an image file."""
    Image = _ensure_pillow()
    return Image.open(path)


def save_image(image: "Image.Image", path: pathlib.Path, **kwargs: Any) -> None:
    """Save an image to disk."""
    Image = _ensure_pillow()
    image.save(path, **kwargs)


def annotate_image(image: "Image.Image") -> "Image.Image":
    """Placeholder for graphical annotation logic."""
    # This is a stub; integrate overlay logic when image-based annotation is added.
    return image.copy()
