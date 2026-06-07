"""Helpers for reproducibility runbook mode in SMLM workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


@dataclass
class ReproducibilityRunbookState:
    """State used to lock parameters and store provenance events."""

    enabled: bool = False
    locked_profiles: Dict[str, dict] = field(default_factory=dict)
    provenance_events: list[dict] = field(default_factory=list)


def utc_now_iso() -> str:
    """Return UTC timestamp in stable ISO format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def lock_profile(state: ReproducibilityRunbookState, method: str, profile: dict) -> None:
    """Lock a method profile for reproducibility mode."""
    state.locked_profiles[str(method)] = dict(profile)


def resolve_profile(state: ReproducibilityRunbookState, method: str, proposed: dict) -> dict:
    """Resolve effective run profile with runbook locking semantics."""
    if not state.enabled:
        return dict(proposed)
    locked = state.locked_profiles.get(str(method))
    if isinstance(locked, dict):
        return dict(locked)
    return dict(proposed)


def append_provenance_event(
    state: ReproducibilityRunbookState,
    *,
    event_type: str,
    payload: dict,
) -> dict:
    """Append immutable provenance event to state."""
    event = {
        "timestamp": utc_now_iso(),
        "event_type": str(event_type),
        "payload": dict(payload),
    }
    state.provenance_events.append(event)
    return event


def export_reproducibility_bundle(
    state: ReproducibilityRunbookState,
    *,
    out_path: Path,
    session_payload: Optional[dict] = None,
) -> Path:
    """Write reproducibility runbook bundle for audit/replay."""
    payload = {
        "schema_version": 1,
        "exported_at": utc_now_iso(),
        "runbook": {
            "enabled": bool(state.enabled),
            "locked_profiles": dict(state.locked_profiles),
            "provenance_events": list(state.provenance_events),
        },
        "session": dict(session_payload or {}),
    }
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    payload["sha256"] = hashlib.sha256(raw).hexdigest()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path
