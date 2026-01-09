"""
Asset Selection Dialog component.

Multi-select dialog for adding saved assets to a watchlist.
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
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
        super().__init__(parent)
        self._assets = assets
        self._existing_symbols = existing_symbols or []
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
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
        self._search_input.setPlaceholderText("Search by symbol...")
        self._search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_input)

        self._clear_search_btn = QPushButton("Clear")
        self._clear_search_btn.clicked.connect(self._clear_search)
        search_layout.addWidget(self._clear_search_btn)

        layout.addLayout(search_layout)

        # Select all / Deselect all buttons
        selection_layout = QHBoxLayout()
        self._select_all_btn = QPushButton("Select All")
        self._select_all_btn.clicked.connect(self._select_all)
        selection_layout.addWidget(self._select_all_btn)

        self._deselect_all_btn = QPushButton("Deselect All")
        self._deselect_all_btn.clicked.connect(self._deselect_all)
        selection_layout.addWidget(self._deselect_all_btn)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Asset list
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        layout.addWidget(self._list_widget)

        # Info label
        self._info_label = QLabel()
        self._info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._info_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        self._add_button = QPushButton("Add Selected")
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
