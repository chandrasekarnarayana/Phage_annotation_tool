"""Unit tests for keyboard-first navigation and undo/redo hardening.

Tests cover:
- Jump-to-frame and jump-to-z commands
- Keyboard shortcut manager and conflict detection
- Transaction boundaries for atomic operations
- Undo/redo consistency across transactions

Tests moved into sibling split modules to keep file size below 300 lines.
"""
