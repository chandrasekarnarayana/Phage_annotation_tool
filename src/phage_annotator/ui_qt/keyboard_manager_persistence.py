"""Default shortcut registration and persistence for KeyboardShortcutManager."""

from __future__ import annotations

from phage_annotator.ui_qt.keyboard_shortcut_types import ShortcutContext, ShortcutDefinition


class KeyboardManagerPersistence:
    """Default shortcut registry and save/load configuration."""

    def _register_default_shortcuts(self) -> None:
        """Register default keyboard shortcuts."""

        # Navigation shortcuts
        nav_shortcuts = [
            ShortcutDefinition(
                id="nav.jump_to_frame",
                category=self.NAVIGATION,
                description="Jump to frame (T)",
                default_sequence="Ctrl+G",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.jump_to_z",
                category=self.NAVIGATION,
                description="Jump to Z slice",
                default_sequence="Ctrl+Shift+G",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.next_frame",
                category=self.NAVIGATION,
                description="Next frame",
                default_sequence="Right",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.prev_frame",
                category=self.NAVIGATION,
                description="Previous frame",
                default_sequence="Left",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.next_z",
                category=self.NAVIGATION,
                description="Next Z slice",
                default_sequence="Down",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="nav.prev_z",
                category=self.NAVIGATION,
                description="Previous Z slice",
                default_sequence="Up",
                context=ShortcutContext.MODALITY_VIEW,
            ),
        ]

        # Undo/Redo shortcuts
        control_shortcuts = [
            ShortcutDefinition(
                id="control.undo",
                category=self.CONTROL,
                description="Undo last action",
                default_sequence="Ctrl+Z",
                context=ShortcutContext.GLOBAL,
            ),
            ShortcutDefinition(
                id="control.redo",
                category=self.CONTROL,
                description="Redo last undone action",
                default_sequence="Ctrl+Y",
                alternative_sequences=["Ctrl+Shift+Z"],
                context=ShortcutContext.GLOBAL,
            ),
        ]

        # Annotation shortcuts
        ann_shortcuts = [
            ShortcutDefinition(
                id="ann.new_annotation",
                category=self.ANNOTATION,
                description="Add annotation at cursor",
                default_sequence="Space",
                context=ShortcutContext.BROWSING,
            ),
            ShortcutDefinition(
                id="ann.delete_selected",
                category=self.ANNOTATION,
                description="Delete selected annotation",
                default_sequence="Delete",
                context=ShortcutContext.EDITING,
            ),
            ShortcutDefinition(
                id="ann.mark_uncertain",
                category=self.ANNOTATION,
                description="Mark selected as uncertain",
                default_sequence="Q",
                context=ShortcutContext.EDITING,
            ),
        ]

        # View shortcuts
        view_shortcuts = [
            ShortcutDefinition(
                id="view.zoom_in",
                category=self.VIEW,
                description="Zoom in",
                default_sequence="Ctrl++",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="view.zoom_out",
                category=self.VIEW,
                description="Zoom out",
                default_sequence="Ctrl+-",
                context=ShortcutContext.MODALITY_VIEW,
            ),
            ShortcutDefinition(
                id="view.fit_window",
                category=self.VIEW,
                description="Fit to window",
                default_sequence="Ctrl+0",
                context=ShortcutContext.MODALITY_VIEW,
            ),
        ]

        # Register all
        for shortcut in nav_shortcuts + control_shortcuts + ann_shortcuts + view_shortcuts:
            self.register_shortcut(shortcut)
