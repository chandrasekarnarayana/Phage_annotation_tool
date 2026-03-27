"""Centralized icon helpers for workflow and tool surfaces."""

from __future__ import annotations

from matplotlib.backends.qt_compat import QtGui, QtWidgets

try:
    import qtawesome as qta
except Exception:  # pragma: no cover - optional dependency fallback
    qta = None

try:
    import simpleicons as _simpleicons  # noqa: F401
except Exception:  # pragma: no cover - optional dependency fallback
    _simpleicons = None


def _qtawesome_icon(name: str, *, color: str, disabled: str | None = None) -> QtGui.QIcon | None:
    if qta is None:
        return None
    try:
        kwargs = {"color": str(color)}
        if disabled is not None:
            kwargs["color_disabled"] = str(disabled)
        return qta.icon(str(name), **kwargs)
    except Exception:
        return None


def _fallback_icon(style: QtWidgets.QStyle, pixmap: QtWidgets.QStyle.StandardPixmap) -> QtGui.QIcon:
    return style.standardIcon(pixmap)


def workflow_sidebar_icon(style: QtWidgets.QStyle, label: str) -> QtGui.QIcon:
    key = str(label or "").strip().lower()
    spec = {
        "lazy loading": ("mdi6.database-search", "#2563eb", QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon),
        "annotation": ("mdi6.map-marker-plus", "#0f766e", QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView),
        "roi": ("mdi6.vector-rectangle", "#b45309", QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton),
        "contrast": ("mdi6.contrast-circle", "#7c3aed", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
    }.get(key)
    if spec is None:
        return _fallback_icon(style, QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
    icon = _qtawesome_icon(spec[0], color=spec[1], disabled="#94a3b8")
    return icon if icon is not None else _fallback_icon(style, spec[2])


def right_sidebar_icon(style: QtWidgets.QStyle, panel_id: str) -> QtGui.QIcon:
    key = str(panel_id or "").strip().lower()
    spec = {
        "annotations": ("mdi6.table-large", "#2563eb", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
        "review_queue": ("mdi6.auto-fix", "#0f766e", QtWidgets.QStyle.StandardPixmap.SP_ArrowRight),
        "advanced_settings": ("mdi6.tune-variant", "#6d28d9", QtWidgets.QStyle.StandardPixmap.SP_FileDialogInfoView),
        "advanced_analysis": ("mdi6.chart-line", "#1d4ed8", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
        "qc_issues": ("mdi6.shield-check", "#b91c1c", QtWidgets.QStyle.StandardPixmap.SP_MessageBoxWarning),
        "collapse": ("mdi6.chevron-double-left", "#475569", QtWidgets.QStyle.StandardPixmap.SP_ArrowLeft),
    }.get(key)
    if spec is None:
        return _fallback_icon(style, QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
    icon = _qtawesome_icon(spec[0], color=spec[1], disabled="#94a3b8")
    return icon if icon is not None else _fallback_icon(style, spec[2])


def tool_icon(style: QtWidgets.QStyle, tool_name: str) -> QtGui.QIcon:
    key = str(tool_name or "").strip().lower()
    spec = {
        "pan_zoom": ("mdi6.cursor-move", "#334155", QtWidgets.QStyle.StandardPixmap.SP_ArrowUp),
        "annotate_point": ("mdi6.crosshairs-gps", "#0f766e", QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton),
        "roi_box": ("mdi6.crop-square", "#b45309", QtWidgets.QStyle.StandardPixmap.SP_DirIcon),
        "roi_circle": ("mdi6.circle-outline", "#b45309", QtWidgets.QStyle.StandardPixmap.SP_DriveNetIcon),
        "roi_edit": ("mdi6.vector-polyline-edit", "#92400e", QtWidgets.QStyle.StandardPixmap.SP_FileDialogListView),
        "profile_line": ("mdi6.chart-bell-curve", "#7c3aed", QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView),
        "eraser": ("mdi6.eraser", "#b91c1c", QtWidgets.QStyle.StandardPixmap.SP_DialogCancelButton),
    }.get(key)
    if spec is None:
        return _fallback_icon(style, QtWidgets.QStyle.StandardPixmap.SP_FileIcon)
    icon = _qtawesome_icon(spec[0], color=spec[1], disabled="#94a3b8")
    return icon if icon is not None else _fallback_icon(style, spec[2])
