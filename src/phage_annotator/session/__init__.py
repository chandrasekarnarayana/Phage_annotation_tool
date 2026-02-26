"""Session management exports.

`SessionController` depends on Qt and may be unavailable in headless
environments; `SessionState` is always available.
"""

from phage_annotator.core.session_state import SessionState

try:  # pragma: no cover - depends on Qt bindings in runtime environment
    from phage_annotator.session.controller import SessionController
except ImportError:  # pragma: no cover
    SessionController = None  # type: ignore[assignment]

__all__ = [
    "SessionController",
    "SessionState",
]
