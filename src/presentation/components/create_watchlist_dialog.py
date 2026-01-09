"""
Create Watchlist Dialog component.

Simple dialog for entering a new watchlist name.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
)


class CreateWatchlistDialog(QDialog):
    """
    Dialog for creating a new watchlist with a custom name.

    Usage:
        dialog = CreateWatchlistDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.get_name()
    """

    def __init__(self, parent=None, existing_names: list = None):
        """
        Initialize the dialog.

        Args:
            parent: Parent widget
            existing_names: List of existing watchlist names (for validation)
        """
        super().__init__(parent)
        self._existing_names = existing_names or []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle("Create New Watchlist")
        self.setMinimumWidth(300)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Label
        label = QLabel("Enter watchlist name:")
        layout.addWidget(label)

        # Name input
        self._name_input = QLineEdit()
        self._name_input.setObjectName("watchlist_name_input")
        self._name_input.setPlaceholderText("e.g., Tech Stocks, Favorites")
        self._name_input.textChanged.connect(self._on_text_changed)
        self._name_input.returnPressed.connect(self._on_ok_clicked)
        layout.addWidget(self._name_input)

        # Error label
        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancel_watchlist_button")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        self._ok_button = QPushButton("Create")
        self._ok_button.setObjectName("create_watchlist_button")
        self._ok_button.setDefault(True)
        self._ok_button.setEnabled(False)
        self._ok_button.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(self._ok_button)

        layout.addLayout(button_layout)

        # Focus the input
        self._name_input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        """Handle text change in input field."""
        name = text.strip()

        if not name:
            self._ok_button.setEnabled(False)
            self._error_label.hide()
        elif name.lower() in [n.lower() for n in self._existing_names]:
            self._ok_button.setEnabled(False)
            self._error_label.setText("A watchlist with this name already exists")
            self._error_label.show()
        else:
            self._ok_button.setEnabled(True)
            self._error_label.hide()

    def _on_ok_clicked(self) -> None:
        """Handle OK button click."""
        name = self._name_input.text().strip()
        if name and name.lower() not in [n.lower() for n in self._existing_names]:
            self.accept()

    def get_name(self) -> str:
        """Get the entered watchlist name."""
        return self._name_input.text().strip()

    @staticmethod
    def get_watchlist_name(
        parent=None, existing_names: list = None
    ) -> tuple[str, bool]:
        """
        Static convenience method to show dialog and get result.

        Args:
            parent: Parent widget
            existing_names: List of existing names for validation

        Returns:
            Tuple of (name, accepted)
        """
        dialog = CreateWatchlistDialog(parent, existing_names)
        result = dialog.exec()
        return dialog.get_name(), result == QDialog.DialogCode.Accepted
