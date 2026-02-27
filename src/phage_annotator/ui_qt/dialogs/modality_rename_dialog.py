"""Modality renaming dialog for user-customizable modality names."""

from __future__ import annotations

from typing import Optional

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets


class ModalityRenamingDialog(QtWidgets.QDialog):
    """Dialog for renaming a modality with validation.
    
    Allows users to change the display name of a modality with:
    - Text validation (alphanumeric + spaces)
    - Reserved name checking (prevents conflicts)
    - Real-time feedback
    """

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        current_name: str = "Modality 1",
        reserved_names: Optional[set[str]] = None,
    ) -> None:
        """Initialize the rename dialog.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget
        current_name : str
            Current modality name
        reserved_names : set[str], optional
            Set of names that cannot be used (to prevent duplicates)
        """
        super().__init__(parent)
        self.setWindowTitle("Rename Modality")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        self.current_name = current_name
        self.reserved_names = reserved_names or set()
        
        self._init_ui()
        self._update_ok_button()
    
    def _init_ui(self) -> None:
        """Initialize the UI layout."""
        layout = QtWidgets.QVBoxLayout()
        
        # Label
        label = QtWidgets.QLabel("Enter new modality name:")
        layout.addWidget(label)
        
        # Text input
        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setText(self.current_name)
        self.name_input.setPlaceholderText("e.g., Ch405, Ch488, DAPI, etc.")
        self.name_input.selectAll()  # Pre-select for easy replacement
        self.name_input.textChanged.connect(self._update_ok_button)
        layout.addWidget(self.name_input)
        
        # Status message
        self.status_label = QtWidgets.QLabel("")
        self.status_label.setStyleSheet("color: #cc0000; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        self.ok_button = QtWidgets.QPushButton("Rename")
        self.ok_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def _update_ok_button(self) -> None:
        """Update OK button state and validation message."""
        new_name = self.name_input.text().strip()
        
        # Check if empty
        if not new_name:
            self.status_label.setText("Name cannot be empty")
            self.ok_button.setEnabled(False)
            return
        
        # Check if same as current
        if new_name == self.current_name:
            self.status_label.setText("Name is unchanged")
            self.ok_button.setEnabled(False)
            return
        
        # Check if reserved
        if new_name in self.reserved_names:
            self.status_label.setText(f"Name '{new_name}' is already in use")
            self.ok_button.setEnabled(False)
            return
        
        # Check if valid (alphanumeric + spaces, no special chars)
        if not self._is_valid_name(new_name):
            self.status_label.setText("Name must contain only letters, numbers, and spaces")
            self.ok_button.setEnabled(False)
            return
        
        # All checks passed
        self.status_label.setText("")
        self.ok_button.setEnabled(True)
    
    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Check if name is valid (alphanumeric + spaces/hyphens/underscores).
        
        Parameters
        ----------
        name : str
            Name to validate
        
        Returns
        -------
        bool
            True if valid, False otherwise
        """
        if not name:
            return False
        
        # Allow letters, numbers, spaces, hyphens, underscores
        for char in name:
            if not (char.isalnum() or char in ' -_'):
                return False
        
        return True
    
    def get_new_name(self) -> str:
        """Get the new modality name entered by user.
        
        Returns
        -------
        str
            Trimmed new name
        """
        return self.name_input.text().strip()
    
    @staticmethod
    def rename_modality(
        parent: QtWidgets.QWidget | None = None,
        current_name: str = "Modality 1",
        reserved_names: Optional[set[str]] = None,
    ) -> tuple[bool, str]:
        """Show dialog and get user's new name choice.
        
        Parameters
        ----------
        parent : QWidget, optional
            Parent widget for dialog
        current_name : str
            Current modality name
        reserved_names : set[str], optional
            Reserved names to prevent duplicate
        
        Returns
        -------
        tuple[bool, str]
            (accepted, new_name) where accepted is True if user clicked OK
        
        Examples
        --------
        >>> accepted, new_name = ModalityRenamingDialog.rename_modality(
        ...     current_name="Modality 1",
        ...     reserved_names={"Modality 2", "Ch488"}
        ... )
        >>> if accepted:
        ...     print(f"Rename to: {new_name}")
        """
        dialog = ModalityRenamingDialog(parent, current_name, reserved_names)
        accepted = dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted
        return accepted, dialog.get_new_name()
