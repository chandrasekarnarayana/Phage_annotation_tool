"""Shared GUI constants and small helpers."""

from __future__ import annotations


# Avoid pulling multi-GB TIFFs fully into RAM; switch to memmap beyond this.
BIG_TIFF_BYTES_THRESHOLD = 512 * 1024 * 1024  # 512 MB
# Toggle verbose cache logging for debugging (loading, projection caching, clearing).
DEBUG_CACHE = False
# Optional FPS overlay for playback diagnostics.
DEBUG_FPS = False
# Small ring buffer size for playback prefetch; trades memory vs latency.
PLAYBACK_BUFFER_SIZE = 5
# Only compute FPS every N frames to keep overhead small.
FPS_UPDATE_STRIDE = 5
# Target FPS for high-speed playback; speed slider sets the requested rate.
DEFAULT_PLAYBACK_FPS = 30
# Async projection threshold (bytes); beyond this, compute mean/std in background.
PROJECTION_ASYNC_BYTES = 128 * 1024 * 1024
# Default interactive downsample factor.
INTERACTIVE_DOWNSAMPLE = 2


class CancelTokenShim:
    """Minimal CancelToken-compatible shim for synchronous jobs."""

    def is_cancelled(self) -> bool:
        return False
