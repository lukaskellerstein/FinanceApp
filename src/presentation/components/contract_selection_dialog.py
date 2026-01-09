"""
Contract Selection Dialog component.

Dialog for selecting from multiple IB contracts when a ticker symbol
matches multiple instruments.
"""

import subprocess
from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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


class ContractSelectionDialog(QDialog):
    """
    Dialog for selecting a contract from multiple IB matches.

    Features:
    - Displays all matching contracts with their details
    - Shows exchange, currency, and security type
    - Double-click to select

    Usage:
        dialog = ContractSelectionDialog(symbol, contract_details_list, parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_cd = dialog.get_selected_contract()
    """

    def __init__(
        self,
        symbol: str,
        contract_details_list: List,
        parent=None,
    ):
        """
        Initialize the dialog.

        Args:
            symbol: The ticker symbol being searched
            contract_details_list: List of ContractDetails from IB
            parent: Parent widget
        """
        # Use top-level window as parent to ensure proper transient relationship on X11/i3
        if parent is not None:
            parent = parent.window()
        super().__init__(
            parent,
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._symbol = symbol
        self._details_list = contract_details_list
        self._selected_index: Optional[int] = None
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setObjectName("contract_selection_dialog")
        self.setWindowTitle(f"Select Contract for {self._symbol}")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Instructions
        label = QLabel(
            f"Found {len(self._details_list)} contracts matching '{self._symbol}'.\n"
            "Please select one:"
        )
        layout.addWidget(label)

        # List widget with contracts
        self._list_widget = QListWidget()
        self._list_widget.setObjectName("contract_selection_list")
        self._list_widget.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self._list_widget)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_list(self) -> None:
        """Populate the list with contract details."""
        self._list_widget.clear()

        for i, cd in enumerate(self._details_list):
            # Build descriptive text for each contract
            contract = cd.contract
            name = cd.long_name or ""
            exchange = (
                getattr(contract, 'primary_exchange', "") or
                getattr(contract, 'exchange', "") or
                ""
            )
            currency = getattr(contract, 'currency', "") or ""
            sec_type = getattr(contract, 'sec_type', "") or ""
            local_symbol = getattr(contract, 'local_symbol', "") or ""

            # Format: "NAME (EXCHANGE, CURRENCY) - Type: SEC_TYPE"
            display_text = name if name else self._symbol
            if exchange or currency:
                display_text += f" ({exchange}"
                if currency:
                    display_text += f", {currency}"
                display_text += ")"
            if local_symbol and local_symbol != self._symbol:
                display_text += f" [{local_symbol}]"
            if sec_type:
                display_text += f" - Type: {sec_type}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store index
            self._list_widget.addItem(item)

        # Select first item by default
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def get_selected_contract(self):
        """
        Get the selected contract details.

        Returns:
            Selected ContractDetails object or None
        """
        selected_item = self._list_widget.currentItem()
        if selected_item:
            selected_index = selected_item.data(Qt.ItemDataRole.UserRole)
            return self._details_list[selected_index]
        return None

    def get_selected_index(self) -> Optional[int]:
        """
        Get the index of the selected contract.

        Returns:
            Index in the original list or None
        """
        selected_item = self._list_widget.currentItem()
        if selected_item:
            return selected_item.data(Qt.ItemDataRole.UserRole)
        return None

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
    def select_contract(
        symbol: str,
        contract_details_list: List,
        parent=None,
    ) -> Tuple[Optional[object], bool]:
        """
        Static convenience method to show dialog and get result.

        Args:
            symbol: The ticker symbol
            contract_details_list: List of ContractDetails from IB
            parent: Parent widget

        Returns:
            Tuple of (selected_contract_details, accepted)
        """
        dialog = ContractSelectionDialog(symbol, contract_details_list, parent)
        result = dialog.exec()
        accepted = result == QDialog.DialogCode.Accepted
        return dialog.get_selected_contract() if accepted else None, accepted
