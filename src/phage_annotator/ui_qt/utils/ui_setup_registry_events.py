"""Extracted method group 3 for UiSetupRegistryMixin."""

from __future__ import annotations

from typing import List, Optional, Tuple

from matplotlib.backends.qt_compat import QtWidgets

from phage_annotator.ui_qt.panels.performance import PerformancePanel
from phage_annotator.ui_qt.panels.registry import PanelSpec
from phage_annotator.ui_qt.utils import ui_docks
from phage_annotator.ui_qt.utils.ui_setup_panels import (
    build_panel_policy_controls,
    refresh_panel_policy_controls,
)



class UiSetupRegistryEventsMixin:
    """Method group 3 extracted from UiSetupRegistryMixin."""

    def _build_sidebar_pages(
        self, display_group: QtWidgets.QGroupBox
    ) -> List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]]:
        """Build sidebar pages for the current workflow."""
        pages: List[Tuple[str, QtWidgets.QStyle.StandardPixmap, QtWidgets.QWidget]] = []

        def _make_scroll(widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
            """Create scroll for the current workflow."""
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
            scroll.setWidget(widget)
            return scroll

        def _dock_button(text: str, panel_id: str, tooltip: str) -> QtWidgets.QPushButton:
            """Handle the dock button helper flow."""
            btn = QtWidgets.QPushButton(text)
            btn.setToolTip(str(tooltip))
            btn.clicked.connect(lambda: self.open_panel(str(panel_id), reason="sidebar_button"))
            return btn

        def _page_shell(
            title: str,
            description: str,
            content: QtWidgets.QWidget,
            *,
            quick_buttons: Optional[List[QtWidgets.QPushButton]] = None,
        ) -> QtWidgets.QWidget:
            """Handle the page shell helper flow."""
            page = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(page)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)

            title_lbl = QtWidgets.QLabel(str(title))
            title_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
            layout.addWidget(title_lbl)

            if str(description or "").strip():
                desc_lbl = QtWidgets.QLabel(str(description))
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet("color: #4b5563;")
                layout.addWidget(desc_lbl)

            if quick_buttons:
                quick_row = QtWidgets.QHBoxLayout()
                quick_row.setSpacing(6)
                for button in quick_buttons:
                    quick_row.addWidget(button)
                quick_row.addStretch(1)
                layout.addLayout(quick_row)

            layout.addWidget(content)
            layout.addStretch(1)
            return _make_scroll(page)

        def _stack_sections(*sections: QtWidgets.QWidget) -> QtWidgets.QWidget:
            """Handle the stack sections helper flow."""
            container = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            for section in sections:
                layout.addWidget(section)
            layout.addStretch(1)
            return container

        def _quick_group(
            title: str,
            description: str,
            buttons: List[QtWidgets.QPushButton],
        ) -> QtWidgets.QWidget:
            """Handle the quick group helper flow."""
            group = QtWidgets.QGroupBox(str(title))
            layout = QtWidgets.QVBoxLayout(group)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(6)
            desc = QtWidgets.QLabel(str(description))
            desc.setWordWrap(True)
            desc.setStyleSheet("color: #4b5563;")
            layout.addWidget(desc)
            for button in buttons:
                layout.addWidget(button)
            return group

        def _build_lazy_loading_section() -> QtWidgets.QWidget:
            """Build lazy loading section for the current workflow."""
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            compare_group = QtWidgets.QGroupBox("Reference Views")
            compare_layout = QtWidgets.QVBoxLayout(compare_group)
            compare_layout.setContentsMargins(8, 8, 8, 8)
            compare_layout.setSpacing(6)
            self.prepare_reference_summary_lbl = QtWidgets.QLabel("Reference views: -")
            self.prepare_reference_summary_lbl.setStyleSheet("color: #455a64;")
            compare_layout.addWidget(self.prepare_reference_summary_lbl)
            layout.addWidget(compare_group)

            sync_group = QtWidgets.QGroupBox("Synchronized Navigation")
            sync_layout = QtWidgets.QVBoxLayout(sync_group)
            sync_layout.setContentsMargins(8, 8, 8, 8)
            sync_layout.setSpacing(6)
            self.prepare_sync_target_lbl = QtWidgets.QLabel("Sync target: -")
            self.prepare_sync_contract_lbl = QtWidgets.QLabel("Sync contract: -")
            self.prepare_sync_panels_lbl = QtWidgets.QLabel("Sync panels: -")
            for label in (
                self.prepare_sync_target_lbl,
                self.prepare_sync_contract_lbl,
                self.prepare_sync_panels_lbl,
            ):
                label.setStyleSheet("color: #455a64;")
                sync_layout.addWidget(label)
            sync_buttons = QtWidgets.QHBoxLayout()
            focus_sync_btn = QtWidgets.QPushButton("Focus Sync Controls")
            focus_sync_btn.setToolTip("Move focus to the bottom playback/sync control strip.")
            focus_sync_btn.clicked.connect(self._focus_playback_controls)
            sync_buttons.addWidget(focus_sync_btn)
            sync_buttons.addStretch(1)
            sync_layout.addLayout(sync_buttons)
            layout.addWidget(sync_group)

            return section

        def _build_roi_page_section() -> QtWidgets.QWidget:
            """Build roi page section for the current workflow."""
            section = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)

            roi_group = QtWidgets.QGroupBox("ROI")
            roi_layout = QtWidgets.QVBoxLayout(roi_group)
            roi_layout.setContentsMargins(8, 8, 8, 8)
            roi_layout.setSpacing(6)
            self.prepare_roi_summary_lbl = QtWidgets.QLabel("ROI: Full field")
            self.prepare_roi_summary_lbl.setStyleSheet("color: #455a64;")
            roi_layout.addWidget(self.prepare_roi_summary_lbl)
            if getattr(self, "_roi_controls_layout", None) is not None:
                roi_layout.addLayout(self._roi_controls_layout)
            roi_buttons = QtWidgets.QHBoxLayout()
            roi_buttons.addWidget(
                _dock_button("ROI Manager", "roi_manager", "Open saved ROI management tools.")
            )
            clear_roi_btn = QtWidgets.QPushButton("Clear ROI")
            clear_roi_btn.setToolTip("Remove the active ROI and return to full field.")
            clear_roi_btn.clicked.connect(self._clear_roi)
            roi_buttons.addWidget(clear_roi_btn)
            roi_buttons.addStretch(1)
            roi_layout.addLayout(roi_buttons)
            layout.addWidget(roi_group)
            layout.addStretch(1)
            return section

        def _trigger_action(action_name: str) -> None:
            """Handle the trigger action helper flow."""
            action = getattr(self, action_name, None)
            if action is not None:
                action.trigger()

        lazy_loading_content = self.explore_panel
        if hasattr(self, "_update_sync_keys_hint"):
            self._update_sync_keys_hint()
        if hasattr(self, "_refresh_prepare_setup_summary"):
            self._refresh_prepare_setup_summary()

        pages.append(
            (
                "Lazy Loading",
                QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon,
                _page_shell(
                    "Lazy Loading",
                    "",
                    lazy_loading_content,
                ),
            )
        )
        pages.append(
            (
                "Annotation",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogContentsView,
                _page_shell(
                    "Annotation",
                    "",
                    self._build_annotate_panel(),
                    quick_buttons=[
                        _dock_button("Annotation Table", "annotations", "Open the annotation table dock."),
                        _dock_button("Assist", "review_queue", "Open assist review and decision tools."),
                        _dock_button("QC", "qc_issues", "Open quality-control issues."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "ROI",
                QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton,
                _page_shell(
                    "ROI",
                    "",
                    _build_roi_page_section(),
                    quick_buttons=[
                        _dock_button("ROI Manager", "roi_manager", "Open the ROI manager."),
                    ],
                ),
            )
        )
        pages.append(
            (
                "Contrast",
                QtWidgets.QStyle.StandardPixmap.SP_FileDialogDetailedView,
                _page_shell(
                    "Contrast",
                    "",
                    display_group,
                    quick_buttons=[
                        _dock_button("Profile", "profile", "Open the line profile."),
                    ],
                ),
            )
        )
        return pages
