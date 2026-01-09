"""
Create Watchlist Dialog component.

Simple dialog for entering a new watchlist name.
"""

import subprocess
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
)


def _move_window_to_parent_workspace(window_title: str, parent_title: str) -> None:
    """Move a window to the same workspace as its parent (i3wm only).

    This uses i3-msg to find the parent window's workspace and move the
    dialog window there. This is needed because i3 doesn't always respect
    X11 transient-for hints for workspace placement.
    """
    try:
        import json
        # Get i3 tree
        result = subprocess.run(
            ["i3-msg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode != 0:
            return

        tree = json.loads(result.stdout)

        # Find both windows
        parent_ws = None
        dialog_con_id = None

        def search_all(node, workspace=None):
            nonlocal parent_ws, dialog_con_id
            if node.get('type') == 'workspace':
                workspace = node.get('num', node.get('name'))

            title = node.get('window_properties', {}).get('title', '') or ''
            if title == parent_title:
                parent_ws = workspace
            if title == window_title:
                dialog_con_id = node.get('id')

            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                search_all(child, workspace)

        search_all(tree)

        # Move dialog to parent's workspace if found
        if parent_ws is not None and dialog_con_id is not None:
            subprocess.run(
                ["i3-msg", f"[con_id={dialog_con_id}] move container to workspace number {parent_ws}"],
                capture_output=True,
                timeout=2
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        # i3-msg not available or failed - ignore
        pass


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
        # Use top-level window as parent to ensure proper transient relationship on X11/i3
        if parent is not None:
            parent = parent.window()
        super().__init__(
            parent,
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._existing_names = existing_names or []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setObjectName("create_watchlist_dialog")
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

    def showEvent(self, event) -> None:
        """Handle show event to move dialog to parent's workspace on i3."""
        super().showEvent(event)
        # Schedule workspace move after window is mapped
        QTimer.singleShot(50, self._move_to_parent_workspace)

    def _move_to_parent_workspace(self) -> None:
        """Move this dialog to the parent window's workspace using i3-msg."""
        parent = self.parent()
        if parent is None:
            return

        parent_title = parent.windowTitle()
        dialog_title = self.windowTitle()

        if parent_title and dialog_title:
            _move_window_to_parent_workspace(dialog_title, parent_title)

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
