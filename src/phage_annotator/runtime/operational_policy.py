"""Runtime policy for memory budgets and background responsiveness."""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_CACHE_BUDGET_MB = 1024
MIN_CACHE_BUDGET_MB = 256
MAX_DEFAULT_CACHE_BUDGET_MB = 4096
MAX_WORKER_THREADS = 4


@dataclass(frozen=True)
class RuntimeOperationalPolicy:
    """Bounded startup settings for responsive GUI operation."""

    max_worker_threads: int
    global_cache_budget_mb: float


def _available_memory_mb() -> int | None:
    """Return available physical memory in MB when the OS exposes it."""
    if not hasattr(os, "sysconf"):
        return None
    try:
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        page_count = int(os.sysconf("SC_PHYS_PAGES"))
    except (OSError, ValueError):
        return None
    if page_size <= 0 or page_count <= 0:
        return None
    return int(page_size * page_count / (1024 * 1024))


def _env_int(name: str) -> int | None:
    """Parse a positive integer environment override."""
    value = os.environ.get(name)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def build_runtime_policy() -> RuntimeOperationalPolicy:
    """Build startup limits for cache memory and background worker count."""
    cpu_count = os.cpu_count() or 2
    default_workers = max(1, min(MAX_WORKER_THREADS, cpu_count - 1))
    workers = _env_int("PHAGE_ANNOTATOR_MAX_WORKERS") or default_workers
    workers = max(1, min(MAX_WORKER_THREADS, workers))

    memory_mb = _available_memory_mb()
    if memory_mb is None:
        default_cache = DEFAULT_CACHE_BUDGET_MB
    else:
        default_cache = max(
            MIN_CACHE_BUDGET_MB,
            min(MAX_DEFAULT_CACHE_BUDGET_MB, int(memory_mb * 0.2)),
        )
    cache_budget = _env_int("PHAGE_ANNOTATOR_CACHE_MB") or default_cache
    cache_budget = max(MIN_CACHE_BUDGET_MB, int(cache_budget))

    return RuntimeOperationalPolicy(
        max_worker_threads=workers,
        global_cache_budget_mb=float(cache_budget),
    )
