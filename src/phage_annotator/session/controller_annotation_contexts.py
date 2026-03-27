"""Annotation-context ownership helpers for N-modality workflows.

This layer keeps annotation ownership explicit without forcing the whole
application to stop using the existing image-keyed point store immediately.
Contexts describe where points belong logically; the actual points still live
under their source image bucket for compatibility.
"""

from __future__ import annotations

from typing import Dict, Optional


class SessionControllerAnnotationContextsMixin:
    """Controller helpers for context-aware annotation ownership and bindings."""

    def _find_annotation_context_spec(
        self,
        panel_key: str,
        *,
        annotation_space: Optional[str] = None,
    ) -> Dict[str, object]:
        """Return an existing context spec for a panel/space pair if one exists."""
        key = str(panel_key or "").strip().lower() or "frame"
        space = str(annotation_space or getattr(self.session_state, "annotation_space", "stack")).strip().lower()
        contexts = dict(getattr(self.session_state, "annotation_contexts", {}) or {})
        for spec in contexts.values():
            current = dict(spec or {})
            if str(current.get("panel_key", "")).strip().lower() != key:
                continue
            if str(current.get("annotation_space", "")).strip().lower() != space:
                continue
            return current
        return {}

    def _panel_source_image_id(self, panel_key: str) -> int:
        """Return the source image id rendered by one canvas/lazy-table panel."""
        key = str(panel_key or "").strip().lower()
        manager = getattr(self.session_state, "modality_manager", None)
        if manager is not None:
            if key.startswith("modality_"):
                try:
                    modality = manager.get_modality(int(key.split("_", 1)[1]))
                    if modality is not None:
                        return int(modality.image_id)
                except Exception:
                    pass
            if key == "frame":
                modality = manager.get_modality(0)
                if modality is not None:
                    return int(modality.image_id)
            if key == "support":
                modality = manager.get_modality(1)
                if modality is not None:
                    return int(modality.image_id)
        if key == "support":
            return int(getattr(self.session_state, "active_support_id", 0))
        return int(getattr(self.session_state, "active_primary_id", 0))

    def _panel_modality_idx(self, panel_key: str) -> Optional[int]:
        """Return the modality index associated with a panel key when available."""
        key = str(panel_key or "").strip().lower()
        if key.startswith("modality_"):
            try:
                return int(key.split("_", 1)[1])
            except Exception:
                return None
        if key == "frame":
            return 0
        if key == "support":
            return 1
        return None

    def _panel_projection_key(self, panel_key: str) -> str:
        """Return the projection kind rendered by a panel."""
        key = str(panel_key or "").strip().lower()
        manager = getattr(self.session_state, "modality_manager", None)
        if manager is not None and key.startswith("modality_"):
            try:
                modality = manager.get_modality(int(key.split("_", 1)[1]))
                if modality is not None:
                    return str(getattr(modality.projection_type, "value", "raw")).strip().lower()
            except Exception:
                pass
        if key in {"mean", "std", "min", "max"}:
            return key
        return "raw"

    def _default_annotation_context_mode(self, panel_key: str) -> str:
        """Choose a scientifically sensible default context mode for a panel."""
        projection = self._panel_projection_key(panel_key)
        if projection != "raw":
            return "shared_source"
        return "independent"

    def annotation_context_key_for_panel(
        self,
        panel_key: str,
        *,
        annotation_space: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> str:
        """Build a stable annotation-context key for a panel."""
        key = str(panel_key or "").strip().lower() or "frame"
        space = str(annotation_space or getattr(self.session_state, "annotation_space", "stack")).strip().lower()
        if space not in {"stack", "projection"}:
            space = "stack"
        source_image_id = self._panel_source_image_id(key)
        ownership = str(mode or self._default_annotation_context_mode(key)).strip().lower()
        if ownership == "shared_source":
            return f"img:{source_image_id}|space:{space}|shared"
        return f"img:{source_image_id}|panel:{key}|space:{space}"

    def ensure_annotation_context_for_panel(
        self,
        panel_key: str,
        *,
        annotation_space: Optional[str] = None,
        writable: bool = True,
    ) -> Dict[str, object]:
        """Return or register the annotation context spec for a panel."""
        key = str(panel_key or "").strip().lower() or "frame"
        space = str(annotation_space or getattr(self.session_state, "annotation_space", "stack")).strip().lower()
        existing = self._find_annotation_context_spec(key, annotation_space=space)
        mode = str(existing.get("mode", self._default_annotation_context_mode(key))).strip().lower()
        ownership_mode = str(existing.get("ownership_mode", mode)).strip().lower()
        if ownership_mode not in {"shared_source", "independent"}:
            ownership_mode = self._default_annotation_context_mode(key)
        context_key = str(existing.get("context_key", "")).strip() or self.annotation_context_key_for_panel(
            key,
            annotation_space=space,
            mode=ownership_mode,
        )
        contexts = dict(getattr(self.session_state, "annotation_contexts", {}) or {})
        spec = dict(contexts.get(context_key, {}) or {})
        spec.update(
            {
                "context_key": context_key,
                "panel_key": key,
                "source_image_id": int(self._panel_source_image_id(key)),
                "annotation_space": space,
                "mode": mode,
                "ownership_mode": ownership_mode,
                "projection": self._panel_projection_key(key),
                "modality_idx": self._panel_modality_idx(key),
                "writable": bool(writable),
            }
        )
        contexts[context_key] = spec
        self.session_state.annotation_contexts = contexts
        return spec

    def current_annotation_context(self) -> Dict[str, object]:
        """Return the context currently selected for annotation writes."""
        target = str(getattr(self.view_state, "annotate_target", "frame")).strip().lower() or "frame"
        return self.ensure_annotation_context_for_panel(target, writable=True)

    def annotations_for_panel(self, panel_key: str) -> list:
        """Return annotations that belong logically to one panel context."""
        spec = self.ensure_annotation_context_for_panel(panel_key, writable=False)
        source_image_id = int(spec["source_image_id"])
        context_key = str(spec["context_key"])
        modality_idx = spec.get("modality_idx")
        mode = str(spec.get("ownership_mode", spec.get("mode", "independent")))
        rows = list(self.session_state.annotations.get(source_image_id, []))
        result = []
        for kp in rows:
            kp_context = str(getattr(kp, "annotation_context", "") or "")
            if kp_context:
                if kp_context == context_key:
                    result.append(kp)
                continue
            kp_modality = getattr(kp, "modality_idx", None)
            if mode == "shared_source":
                if kp_modality in (None, modality_idx):
                    result.append(kp)
                continue
            if modality_idx is None:
                if kp_modality is None:
                    result.append(kp)
            elif kp_modality == modality_idx:
                result.append(kp)
        return result

    def set_annotation_context_mode_for_panel(
        self,
        panel_key: str,
        mode: str,
        *,
        annotation_space: Optional[str] = None,
    ) -> Dict[str, object]:
        """Update annotation ownership mode for a panel.

        Modes:
        - ``independent``: own annotation context/file binding
        - ``shared_source``: share the source image context across projections
        - ``read_only``: keep the current ownership context but remove write access
        """
        key = str(panel_key or "").strip().lower() or "frame"
        desired = str(mode or "").strip().lower()
        if desired not in {"independent", "shared_source", "read_only"}:
            desired = "independent"
        current = self.ensure_annotation_context_for_panel(key, annotation_space=annotation_space, writable=desired != "read_only")
        space = str(current.get("annotation_space", getattr(self.session_state, "annotation_space", "stack")))
        old_key = str(current.get("context_key", ""))
        old_ownership = str(current.get("ownership_mode", current.get("mode", "independent")))
        new_ownership = old_ownership if desired == "read_only" else desired
        new_key = old_key
        if new_ownership != old_ownership:
            new_key = self.annotation_context_key_for_panel(key, annotation_space=space, mode=new_ownership)

        contexts = dict(getattr(self.session_state, "annotation_contexts", {}) or {})
        spec = dict(current)
        spec["context_key"] = str(new_key)
        spec["mode"] = desired
        spec["ownership_mode"] = new_ownership
        spec["writable"] = bool(desired != "read_only")
        if old_key != new_key:
            contexts.pop(old_key, None)
            bindings = dict(getattr(self.session_state, "annotation_file_bindings", {}) or {})
            binding = dict(bindings.pop(old_key, {}) or {})
            if binding:
                binding["context_key"] = str(new_key)
                bindings[str(new_key)] = binding
            self.session_state.annotation_file_bindings = bindings
            source_image_id = int(spec.get("source_image_id", self._panel_source_image_id(key)))
            rows = list(self.session_state.annotations.get(source_image_id, []))
            for kp in rows:
                kp_context = str(getattr(kp, "annotation_context", "") or "")
                if kp_context == old_key:
                    kp.annotation_context = str(new_key)
        contexts[str(new_key)] = spec
        self.session_state.annotation_contexts = contexts
        return spec

    def bind_annotation_file_to_panel(
        self,
        panel_key: str,
        path: str,
        *,
        fmt: str,
        mtime: float | None = None,
        annotation_space: Optional[str] = None,
    ) -> None:
        """Record an annotation-file binding for a panel context."""
        spec = self.ensure_annotation_context_for_panel(panel_key, annotation_space=annotation_space)
        bindings = dict(getattr(self.session_state, "annotation_file_bindings", {}) or {})
        bindings[str(spec["context_key"])] = {
            "context_key": str(spec["context_key"]),
            "panel_key": str(spec["panel_key"]),
            "path": str(path),
            "format": str(fmt),
            "mtime": None if mtime is None else float(mtime),
            "source_image_id": int(spec["source_image_id"]),
            "annotation_space": str(spec["annotation_space"]),
        }
        self.session_state.annotation_file_bindings = bindings

    def annotation_binding_for_panel(self, panel_key: str) -> Dict[str, object]:
        """Return the current file binding for a panel, if any."""
        spec = self.ensure_annotation_context_for_panel(panel_key, writable=False)
        return dict(
            dict(getattr(self.session_state, "annotation_file_bindings", {}) or {}).get(
                str(spec["context_key"]),
                {},
            )
            or {}
        )

    def clear_annotation_binding_for_panel(
        self,
        panel_key: str,
        *,
        annotation_space: Optional[str] = None,
    ) -> None:
        """Remove any file binding for a panel context."""
        spec = self.ensure_annotation_context_for_panel(panel_key, annotation_space=annotation_space, writable=False)
        bindings = dict(getattr(self.session_state, "annotation_file_bindings", {}) or {})
        bindings.pop(str(spec.get("context_key", "")), None)
        self.session_state.annotation_file_bindings = bindings
