"""
Asset Selection Dialog component.

Multi-select dialog for adding saved assets to a watchlist.
"""

import subprocess
from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QAbstractItemView,
)

from src.domain.entities.asset import Asset


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

        # Find workspaces for both windows
        def find_window_workspace(node, workspace=None):
            if node.get('type') == 'workspace':
                workspace = node.get('num', node.get('name'))

            title = node.get('window_properties', {}).get('title', '') or ''
            if title == parent_title:
                return ('parent', workspace, node.get('id'))
            if title == window_title:
                return ('dialog', workspace, node.get('id'))

            for child in node.get('nodes', []) + node.get('floating_nodes', []):
                found = find_window_workspace(child, workspace)
                if found:
                    return found
            return None

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


class AssetSelectionDialog(QDialog):
    """
    Dialog for selecting multiple assets from saved assets.

    Features:
    - Displays all saved assets as checkable items
    - Search/filter functionality
    - Select all / Deselect all buttons
    - Shows already-added items as disabled

    Usage:
        dialog = AssetSelectionDialog(assets, existing_symbols, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected = dialog.get_selected_symbols()
    """

    def __init__(
        self,
        assets: List[Asset],
        existing_symbols: List[str] = None,
        parent=None,
    ):
        """
        Initialize the dialog.

        Args:
            assets: List of available Asset objects
            existing_symbols: Symbols already in the watchlist (shown as disabled)
            parent: Parent widget
        """
        # Store original parent for workspace detection
        self._original_parent = parent
        # Use top-level window as parent to ensure proper transient relationship on X11/i3
        if parent is not None:
            parent = parent.window()
        super().__init__(
            parent,
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._assets = assets
        self._existing_symbols = existing_symbols or []
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setObjectName("asset_selection_dialog")
        self.setWindowTitle("Add Assets to Watchlist")
        self.setMinimumSize(400, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header_label = QLabel("Select assets to add:")
        layout.addWidget(header_label)

        # Search input
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setObjectName("asset_search_input")
        self._search_input.setPlaceholderText("Search by symbol...")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)

        self._clear_search_btn = QPushButton("Clear")
        self._clear_search_btn.setObjectName("asset_clear_search_button")
        self._clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self._clear_search_btn)

        layout.addLayout(search_layout)

        # Select all / Deselect all buttons
        selection_layout = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.setObjectName("asset_select_all_button")
        self._select_all_btn.clicked.connect(self._select_all)
        selection_layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.setObjectName("asset_deselect_all_button")
        self._deselect_all_btn.clicked.connect(self._deselect_all)
        selection_layout.addWidget(self._deselect_all_btn)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Asset list
        self._list_widget = QListWidget()
        self._list_widget.setObjectName("asset_list")
        self._list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self._list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list_widget)

        # Info label
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._info_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("asset_cancel_button")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        self._add_button = QPushButton("Add Selected")
        self._add_button.setObjectName("asset_add_selected_button")
        self._add_button.setDefault(True)
        self._add_button.clicked.connect(self.accept)
        button_layout.addWidget(self._add_button)

        layout.addLayout(button_layout)

        # Focus search
        self._search_input.setFocus()

    def _populate_list(self) -> None:
        """Populate the list with assets."""
        self._list_widget.clear()

        for asset in self._assets:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, asset.symbol)

            # Create display text
            description = asset.short_description or ""
            if description:
                display_text = f"{asset.symbol} - {description}"
            else:
                display_text = asset.symbol

            item.setText(display_text)

            # Check if already in watchlist
            if asset.symbol in self._existing_symbols:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setCheckState(Qt.CheckState.Checked)
                item.setToolTip("Already in watchlist")
            else:
                item.setFlags(
                    item.flags() | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(Qt.CheckState.Unchecked)

            self._list_widget.addItem(item)

        self._update_info_label()

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """Handle item check state change."""
        self._update_info_label()

    def _on_search_changed(self, text: str) -> None:
        """Filter the list based on search text."""
        search_text = text.lower()

        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            symbol = item.data(Qt.ItemDataRole.UserRole)
            display_text = item.text().lower()

            # Show if search matches symbol or display text
            visible = not search_text or (
                search_text in symbol.lower() or
                search_text in display_text
            )
            item.setHidden(not visible)

    def _clear_search(self) -> None:
        """Clear the search input."""
        self._search_input.clear()

    def _select_all(self) -> None:
        """Select all visible, enabled items."""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if not item.isHidden() and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                symbol = item.data(Qt.ItemDataRole.UserRole)
                if symbol not in self._existing_symbols:
                    item.setCheckState(Qt.CheckState.Checked)
        self._update_info_label()

    def _deselect_all(self) -> None:
        """Deselect all visible items."""
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if not item.isHidden() and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                symbol = item.data(Qt.ItemDataRole.UserRole)
                if symbol not in self._existing_symbols:
                    item.setCheckState(Qt.CheckState.Unchecked)
        self._update_info_label()

    def _update_info_label(self) -> None:
        """Update the info label with selection count."""
        selected = self._get_selected_count()
        total = len(self._assets) - len(self._existing_symbols)
        self._info_label.setText(
            f"{selected} of {total} available assets selected"
        )
        self._add_button.setEnabled(selected > 0)

    def _get_selected_count(self) -> int:
        """Get the number of selected items."""
        count = 0
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            symbol = item.data(Qt.ItemDataRole.UserRole)
            if (
                item.checkState() == Qt.CheckState.Checked and
                symbol not in self._existing_symbols
            ):
                count += 1
        return count

    def get_selected_symbols(self) -> List[str]:
        """Get the list of selected symbols (excluding already added)."""
        selected = []
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            symbol = item.data(Qt.ItemDataRole.UserRole)
            if (
                item.checkState() == Qt.CheckState.Checked and
                symbol not in self._existing_symbols
            ):
                selected.append(symbol)
        return selected

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
    def select_assets(
        assets: List[Asset],
        existing_symbols: List[str] = None,
        parent=None,
    ) -> tuple[List[str], bool]:
        """
        Static convenience method to show dialog and get result.

        Args:
            assets: Available assets
            existing_symbols: Symbols already in watchlist
            parent: Parent widget

        Returns:
            Tuple of (selected_symbols, accepted)
        """
        dialog = AssetSelectionDialog(assets, existing_symbols, parent)
        result = dialog.exec()
        return dialog.get_selected_symbols(), result == QDialog.DialogCode.Accepted
