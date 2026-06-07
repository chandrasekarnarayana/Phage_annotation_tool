"""Conflict detection and context management for keyboard shortcuts."""

from __future__ import annotations

from typing import Set

from phage_annotator.ui_qt.keyboard_shortcut_types import (
    ShortcutContext,
    ShortcutDefinition,
    ShortcutConflict,
)


class KeyboardManagerConflicts:
    """Conflict detection and shortcut context enable/disable logic."""

    def _detect_conflicts_for_shortcut(
        self,
        shortcut: ShortcutDefinition,
    ) -> None:
        """Detect conflicts for a single shortcut.

        Parameters
        ----------
        shortcut : ShortcutDefinition
            Shortcut to check.
        """
        if not shortcut.enabled:
            return

        for seq in shortcut.all_sequences():
            other_shortcuts = self._sequences_to_shortcuts.get(seq, [])

            for other in other_shortcuts:
                if other.id == shortcut.id or not other.enabled:
                    continue

                # Check if contexts are compatible (both active at same time)
                if self._contexts_conflict(shortcut.context, other.context):
                    # Check if already reported
                    conflict = ShortcutConflict(
                        shortcut_a=shortcut,
                        shortcut_b=other,
                        sequence=seq,
                    )

                    if not any(
                        (c.shortcut_a.id == conflict.shortcut_a.id and
                         c.shortcut_b.id == conflict.shortcut_b.id and
                         c.sequence == conflict.sequence)
                        for c in self._conflicts
                    ):
                        self._conflicts.append(conflict)

    @staticmethod
    def _contexts_conflict(
        ctx1: ShortcutContext,
        ctx2: ShortcutContext,
    ) -> bool:
        """Check if two contexts can be active simultaneously.

        Parameters
        ----------
        ctx1, ctx2 : ShortcutContext
            Contexts to check.

        Returns
        -------
        bool
            True if both contexts can be active at the same time.
        """
        # TEXT_INPUT never conflicts (it disables all others)
        if ctx1 == ShortcutContext.TEXT_INPUT or ctx2 == ShortcutContext.TEXT_INPUT:
            return False

        # GLOBAL is compatible with everything
        if ctx1 == ShortcutContext.GLOBAL or ctx2 == ShortcutContext.GLOBAL:
            return True

        # EDITING and BROWSING are mutually exclusive
        if {ctx1, ctx2} == {ShortcutContext.EDITING, ShortcutContext.BROWSING}:
            return False

        # Same context always conflicts
        return ctx1 == ctx2

    def set_context_disabled(
        self,
        context: ShortcutContext,
        disabled: bool = True,
    ) -> None:
        """Disable all shortcuts in a specific context.

        Parameters
        ----------
        context : ShortcutContext
            Context to disable/enable.
        disabled : bool, default True
            If True, disable; if False, enable.
        """
        if disabled:
            self._disabled_contexts.add(context)
        else:
            self._disabled_contexts.discard(context)

    def is_context_active(self, context: ShortcutContext) -> bool:
        """Check if a context is currently active.

        Parameters
        ----------
        context : ShortcutContext
            Context to check.

        Returns
        -------
        bool
            True if context is active, False if disabled.
        """
        return context not in self._disabled_contexts
