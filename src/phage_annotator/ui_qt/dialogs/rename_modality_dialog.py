"""Dialog for renaming a modality with validation.

Features:
- Text input for new name
- Reserved name validation (prevents system names)
- Real-time validation feedback
- Character limit enforcement
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Set

from PyQt5 import QtCore, QtWidgets

if TYPE_CHECKING:
    pass


class RenameModalityDialog(QtWidgets.QDialog):
    """Dialog for renaming a modality with validation.
    
    Features:
    - Prevents reserved names (Modality 1, frame, mean, std, support)
    - Enforces character limits (max 50 chars)
    - Allows alphanumeric + spaces + common symbols
    - Shows validation feedback
    """
    
    # Reserved names that cannot be used
    RESERVED_NAMES = {
        "frame",
        "mean",
        "std",
        "support",
        "raw",
    }
    
    def __init__(
        self,
        current_name: str,
        existing_names: Optional[Set[str]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize rename dialog.
        
        Parameters
        ----------
        current_name : str
            Current modality name (for display).
        existing_names : set[str], optional
            Set of other modality names to check for duplicates.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__(parent)
        self.current_name = current_name
        self.existing_names = existing_names or set()
        self.setWindowTitle(f"Rename Modality: {current_name}")
        self.setModal(True)
        self.setMinimumWidth(350)
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the dialog layout."""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Description
        desc = QtWidgets.QLabel(f"Enter new name for modality: <b>{self.current_name}</b>")
        layout.addWidget(desc)
        
        # Text input
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setText(self.current_name)
        self.name_input.setMaxLength(50)
        self.name_input.selectAll()  # Select all text for easy replacement
        self.name_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.name_input)
        
        # Validation feedback
        self.feedback_label = QtWidgets.QLabel("")
        self.feedback_label.setStyleSheet("color: red; font-size: 11px;")
        layout.addWidget(self.feedback_label)
        
        # Character count
        self.char_count_label = QtWidgets.QLabel("0/50 characters")
        self.char_count_label.setStyleSheet("font-size: 11px; color: gray;")
        layout.addWidget(self.char_count_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        ok_btn = QtWidgets.QPushButton("Rename")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.ok_button = ok_btn
        self.name_input.setFocus()
    
    def _on_text_changed(self, text: str) -> None:
        """Handle text change in input field."""
        # Update character count
        count = len(text)
        self.char_count_label.setText(f"{count}/50 characters")
        
        # Validate and provide feedback
        feedback = self._validate_name(text)
        self.feedback_label.setText(feedback)
        
        # Enable OK button only if valid
        is_valid = not feedback
        self.ok_button.setEnabled(is_valid)
    
    def _validate_name(self, name: str) -> str:
        """Validate modality name.
        
        Parameters
        ----------
        name : str
            Name to validate.
        
        Returns
        -------
        str
            Error message if invalid, empty string if valid.
        """
        # Check if empty
        if not name or not name.strip():
            return "Name cannot be empty"
        
        # Check for reserved names (case-insensitive)
        if name.lower() in self.RESERVED_NAMES:
            return f"'{name}' is a reserved name - please choose another"
        
        # Check for duplicates (case-insensitive, excluding current name)
        for existing in self.existing_names:
            if existing.lower() == name.lower() and existing.lower() != self.current_name.lower():
                return f"'{name}' already exists - please choose a unique name"
        
        # Check for valid characters (alphanumeric, spaces, hyphen, underscore, parentheses)
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -_()")
        if not all(c in valid_chars for c in name):
            return "Name contains invalid characters (use alphanumeric, spaces, -, _, or parentheses)"
        
        # Valid!
        return ""
    
    def get_new_name(self) -> str:
        """Get the new modality name.
        
        Returns
        -------
        str
            The validated new name.
        """
        return self.name_input.text().strip()


def show_rename_modality_dialog(
    current_name: str,
    existing_names: Optional[Set[str]] = None,
    parent: Optional[QtWidgets.QWidget] = None,
) -> Optional[str]:
    """Convenience function to show rename dialog and return result.
    
    Parameters
    ----------
    current_name : str
        Current modality name.
    existing_names : set[str], optional
        Set of other modality names.
    parent : QWidget, optional
        Parent widget.
    
    Returns
    -------
    str | None
        New name if user clicked OK, None if clicked Cancel.
    """
    dialog = RenameModalityDialog(current_name, existing_names, parent)
    if dialog.exec_() == QtWidgets.QDialog.Accepted:
        return dialog.get_new_name()
    return None
