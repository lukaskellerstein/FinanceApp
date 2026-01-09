"""
Contract Selection Dialog component.

Dialog for selecting from multiple IB contracts when a ticker symbol
matches multiple instruments.
"""

from typing import List, Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QDialogButtonBox,
)


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
        super().__init__(parent)
        self._symbol = symbol
        self._details_list = contract_details_list
        self._selected_index: Optional[int] = None
        self._setup_ui()
        self._populate_list()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
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
