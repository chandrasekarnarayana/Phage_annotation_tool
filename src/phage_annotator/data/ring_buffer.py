"""Thread-safe ring buffer and block prefetcher for playback.

Contiguous block reads reduce disk seeks when data is memmap-backed, which
helps sustain high-FPS playback without frame underruns.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional, Tuple

import numpy as np


@dataclass
class BufferStats:
    """Snapshot of ring buffer occupancy."""

    filled: int
    capacity: int


class FrameRingBuffer:
    """Thread-safe ring buffer for sequential playback frames.

    Frames are stored as (t_index, frame) pairs. The buffer is optimized for
    sequential access and avoids duplicates when refilling after a seek.
    """

    def __init__(self, capacity: int) -> None:
        self._capacity = int(max(1, capacity))
        self._queue: Deque[Tuple[int, np.ndarray]] = deque()
        self._indices: set[int] = set()
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def reset(self) -> None:
        with self._lock:
            self._queue.clear()
            self._indices.clear()

    def push_block(self, t_start: int, frames: np.ndarray) -> int:
        """Append a contiguous block of frames if space is available."""
        added = 0
        if frames.size == 0:
            return added
        with self._lock:
            for offset in range(frames.shape[0]):
                if len(self._queue) >= self._capacity:
                    break
                t_idx = int(t_start + offset)
                if t_idx in self._indices:
                    continue
                self._queue.append((t_idx, frames[offset]))
                self._indices.add(t_idx)
                added += 1
        return added

    def pop(self) -> Optional[Tuple[int, np.ndarray]]:
        """Pop the next frame, or None when the buffer is empty."""
        with self._lock:
            if not self._queue:
                return None
            t_idx, frame = self._queue.popleft()
            self._indices.discard(t_idx)
        return t_idx, frame

    def stats(self) -> BufferStats:
        with self._lock:
            return BufferStats(filled=len(self._queue), capacity=self._capacity)


class BlockPrefetcher:
    """Background prefetcher that reads contiguous frame blocks.

    The prefetcher fills the ring buffer up to ``block_size * max_inflight`` to
    keep reads sequential and reduce disk seeks on memmap-backed stacks.
    """

    def __init__(
        self,
        read_block: Callable[[int, int, int], np.ndarray],
        ring: FrameRingBuffer,
        block_size: int,
        max_inflight_blocks: int,
        stop_event: threading.Event,
    ) -> None:
        self._read_block = read_block
        self._ring = ring
        self._stop_event = stop_event
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._block_size = int(max(1, block_size))
        self._max_inflight_blocks = int(max(1, max_inflight_blocks))
        self._t_max = 0
        self._z_idx = 0
        self._loop = False
        self._next_index: Optional[int] = None
        self._reset_requested = False

    def configure(self, block_size: int, max_inflight_blocks: int) -> None:
        self._block_size = int(max(1, block_size))
        self._max_inflight_blocks = int(max(1, max_inflight_blocks))

    def start(self, current_t: int, t_max: int, z_idx: int, loop: bool) -> None:
        """Start (or restart) prefetching from the next frame after current_t."""
        self.request_jump(current_t, t_max, z_idx, loop)
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def request_jump(self, current_t: int, t_max: int, z_idx: int, loop: bool) -> None:
        """Reset the prefetch cursor to a new target index."""
        with self._lock:
            self._t_max = int(max(0, t_max))
            self._z_idx = int(max(0, z_idx))
            self._loop = bool(loop)
            self._next_index = int(current_t + 1)
            self._reset_requested = True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                t_max = self._t_max
                z_idx = self._z_idx
                loop = self._loop
                next_index = self._next_index
                reset = self._reset_requested
                if reset:
                    self._reset_requested = False
            if next_index is None:
                time.sleep(0.01)
                continue
            if reset:
                self._ring.reset()
            stats = self._ring.stats()
            target_fill = min(stats.capacity, self._block_size * self._max_inflight_blocks)
            if stats.filled >= target_fill:
                time.sleep(0.002)
                continue
            if next_index > t_max:
                if loop:
                    next_index = 0
                else:
                    self._stop_event.set()
                    time.sleep(0.01)
                    continue
            t_start = next_index
            t_stop = min(t_start + self._block_size, t_max + 1)
            block = self._read_block(t_start, t_stop, z_idx)
            self._ring.push_block(t_start, block)
            next_index = t_stop
            if loop and next_index > t_max:
                next_index = 0
            with self._lock:
                self._next_index = next_index
            time.sleep(0.001)
