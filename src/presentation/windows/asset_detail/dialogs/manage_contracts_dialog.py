"""
Manage Contracts Dialog for Futures Assets.

Dialog for adding and removing contracts from a futures asset.
Fetches available contracts from Interactive Brokers.
"""

import json
import logging
import subprocess
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QAbstractItemView,
    QFrame,
    QMessageBox,
)

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset
from src.domain.entities.contract import FutureContract
from src.domain.entities.contract_details import ContractDetails

log = logging.getLogger("CellarLogger")


class ManageContractsDialog(QDialog):
    """
    Dialog for managing contracts on a futures asset.

    Features:
    - Shows current contracts with data status
    - Fetches available contracts from IB broker
    - Add/remove contracts
    - Auto-saves changes

    Signals:
        contracts_changed: Emitted when contracts are added or removed
    """

    contracts_changed = pyqtSignal()

    def __init__(self, asset: Asset, parent=None):
        """
        Initialize the dialog.

        Args:
            asset: The futures asset to manage
            parent: Parent widget
        """
        super().__init__(parent)
        self._asset = asset
        self._parent_window = parent  # Store for workspace management
        self._available_contracts: List[ContractDetails] = []
        self._setup_ui()
        self._load_current_contracts()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        self.setWindowTitle(f"Manage Contracts - {self._asset.symbol}")
        self.setMinimumWidth(800)
        self.setMinimumHeight(1000)
        self.resize(900, 1100)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ========== CURRENT CONTRACTS SECTION ==========
        current_label = QLabel("Current Contracts:")
        current_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(current_label)

        # Current contracts table
        self._current_table = QTableWidget()
        self._current_table.setObjectName("current_contracts_table")
        self._current_table.setColumnCount(5)
        self._current_table.setHorizontalHeaderLabels(
            ["Local Symbol", "Expiration", "Exchange", "Contract Month", "Has Data"]
        )
        self._current_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._current_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._current_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._current_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._current_table)

        # Remove button
        remove_layout = QHBoxLayout()
        remove_layout.addStretch()
        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.setObjectName("remove_contract_button")
        self._remove_btn.clicked.connect(self._remove_selected)
        remove_layout.addWidget(self._remove_btn)
        layout.addLayout(remove_layout)

        # ========== SEPARATOR ==========
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # ========== AVAILABLE FROM BROKER SECTION ==========
        available_header = QHBoxLayout()
        available_label = QLabel("Available from Broker:")
        available_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        available_header.addWidget(available_label)
        available_header.addStretch()

        self._fetch_btn = QPushButton("Fetch Contracts")
        self._fetch_btn.setObjectName("fetch_contracts_button")
        self._fetch_btn.clicked.connect(self._fetch_from_broker)
        available_header.addWidget(self._fetch_btn)
        layout.addLayout(available_header)

        # Available contracts table
        self._available_table = QTableWidget()
        self._available_table.setObjectName("available_contracts_table")
        self._available_table.setColumnCount(4)
        self._available_table.setHorizontalHeaderLabels(
            ["Local Symbol", "Expiration", "Exchange", "Contract Month"]
        )
        self._available_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._available_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._available_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._available_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self._available_table)

        # Add and Close buttons
        button_layout = QHBoxLayout()
        self._add_btn = QPushButton("Add Selected")
        self._add_btn.setObjectName("add_contract_button")
        self._add_btn.clicked.connect(self._add_selected)
        button_layout.addWidget(self._add_btn)

        button_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("close_dialog_button")
        self._close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self._close_btn)

        layout.addLayout(button_layout)

    def _load_current_contracts(self) -> None:
        """Load current contracts from asset into the table."""
        self._current_table.setRowCount(0)
        app = get_app()

        for cd in self._asset.contract_details:
            row = self._current_table.rowCount()
            self._current_table.insertRow(row)

            contract = cd.contract
            local_symbol = contract.local_symbol or ""
            last_trade_date = contract.last_trade_date or ""
            exchange = contract.exchange or ""
            contract_month = cd.contract_month or ""

            # Format expiration date
            expiration = ""
            if last_trade_date and len(last_trade_date) == 8:
                expiration = f"{last_trade_date[:4]}-{last_trade_date[4:6]}-{last_trade_date[6:]}"

            # Check if data exists in pystore
            has_data = "No"
            try:
                full_symbol = f"{local_symbol}-{last_trade_date}"
                hist_data = app.historical_data_service.get_historical_data(
                    full_symbol, "1 day"
                )
                if hist_data is not None and not hist_data.empty:
                    has_data = f"Yes ({len(hist_data)} bars)"
            except Exception:
                pass

            self._current_table.setItem(row, 0, QTableWidgetItem(local_symbol))
            self._current_table.setItem(row, 1, QTableWidgetItem(expiration))
            self._current_table.setItem(row, 2, QTableWidgetItem(exchange))
            self._current_table.setItem(row, 3, QTableWidgetItem(contract_month))
            self._current_table.setItem(row, 4, QTableWidgetItem(has_data))

    def _fetch_from_broker(self) -> None:
        """Fetch available contracts from IB broker."""
        app = get_app()

        if not app.broker_client or not app.broker_client.is_connected():
            QMessageBox.warning(
                self,
                "Not Connected",
                "Please connect to Interactive Brokers first.",
            )
            return

        self._fetch_btn.setEnabled(False)
        self._fetch_btn.setText("Fetching...")

        # Create a contract for searching
        search_contract = FutureContract.create(
            symbol=self._asset.symbol,
            exchange="",  # Empty to get all exchanges
        )

        def on_contracts_received(contracts: List[ContractDetails]):
            # Filter out contracts already in the asset
            existing_symbols = {
                cd.contract.local_symbol for cd in self._asset.contract_details
            }
            self._available_contracts = [
                cd
                for cd in contracts
                if cd.contract.local_symbol not in existing_symbols
            ]

            # Update UI on main thread
            self._populate_available_table()
            self._fetch_btn.setEnabled(True)
            self._fetch_btn.setText("Fetch Contracts")

        # Fetch from broker
        app.asset_service.fetch_contract_details(
            asset_type="FUTURE",
            contract=search_contract,
            callback=on_contracts_received,
        )

    def _populate_available_table(self) -> None:
        """Populate the available contracts table."""
        self._available_table.setRowCount(0)

        # Sort by last trade date (newest first)
        sorted_contracts = sorted(
            self._available_contracts,
            key=lambda cd: cd.contract.last_trade_date or "",
            reverse=True,
        )

        for cd in sorted_contracts:
            row = self._available_table.rowCount()
            self._available_table.insertRow(row)

            contract = cd.contract
            local_symbol = contract.local_symbol or ""
            last_trade_date = contract.last_trade_date or ""
            exchange = contract.exchange or ""
            contract_month = cd.contract_month or ""

            # Format expiration date
            expiration = ""
            if last_trade_date and len(last_trade_date) == 8:
                expiration = f"{last_trade_date[:4]}-{last_trade_date[4:6]}-{last_trade_date[6:]}"

            self._available_table.setItem(row, 0, QTableWidgetItem(local_symbol))
            self._available_table.setItem(row, 1, QTableWidgetItem(expiration))
            self._available_table.setItem(row, 2, QTableWidgetItem(exchange))
            self._available_table.setItem(row, 3, QTableWidgetItem(contract_month))

    def _add_selected(self) -> None:
        """Add the selected contracts from available table to the asset."""
        selected_rows = set(item.row() for item in self._available_table.selectedItems())

        if not selected_rows:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select one or more contracts to add.",
            )
            return

        # Get the contracts from our stored list
        # The table is sorted by last_trade_date descending
        sorted_contracts = sorted(
            self._available_contracts,
            key=lambda cd: cd.contract.last_trade_date or "",
            reverse=True,
        )

        # Collect contracts to add
        contracts_to_add = []
        for row in selected_rows:
            if row < len(sorted_contracts):
                contracts_to_add.append(sorted_contracts[row])

        if not contracts_to_add:
            return

        # Add via service
        app = get_app()
        added_symbols = []
        for cd in contracts_to_add:
            app.asset_service.add_contract_to_asset(self._asset, cd)
            self._available_contracts.remove(cd)
            added_symbols.append(cd.contract.local_symbol)

        # Refresh tables
        self._load_current_contracts()
        self._populate_available_table()

        # Emit signal
        self.contracts_changed.emit()

        log.info(f"Added {len(added_symbols)} contracts to {self._asset.symbol}: {', '.join(added_symbols)}")

    def _remove_selected(self) -> None:
        """Remove the selected contracts from the asset."""
        selected_rows = set(item.row() for item in self._current_table.selectedItems())

        if not selected_rows:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select one or more contracts to remove.",
            )
            return

        # Get local symbols from selected rows
        local_symbols = []
        for row in selected_rows:
            local_symbol_item = self._current_table.item(row, 0)
            if local_symbol_item:
                local_symbols.append(local_symbol_item.text())

        if not local_symbols:
            return

        # Confirm removal
        if len(local_symbols) == 1:
            message = f"Remove contract {local_symbols[0]} from {self._asset.symbol}?"
        else:
            symbols_list = ", ".join(local_symbols)
            message = f"Remove {len(local_symbols)} contracts from {self._asset.symbol}?\n\n{symbols_list}"

        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"{message}\n\nThis will also delete the historical data for these contracts.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Remove each selected contract
        app = get_app()
        removed_symbols = []

        for local_symbol in local_symbols:
            # Find the contract details
            removed_cd = None
            for cd in self._asset.contract_details:
                if cd.contract.local_symbol == local_symbol:
                    removed_cd = cd
                    break

            if removed_cd:
                # Delete historical data first
                contract = removed_cd.contract
                last_trade_date = contract.last_trade_date or ""
                # Build the storage symbol: {base_symbol}/{local_symbol}-{last_trade_date}
                storage_symbol = f"{self._asset.symbol}/{local_symbol}-{last_trade_date}"
                try:
                    app.historical_data_service.delete_historical_data(
                        storage_symbol, "1 day"
                    )
                    log.info(f"Deleted historical data for {storage_symbol}")
                except Exception as e:
                    log.warning(f"Failed to delete historical data for {storage_symbol}: {e}")

            success = app.asset_service.remove_contract_from_asset(
                self._asset, local_symbol
            )

            if success:
                removed_symbols.append(local_symbol)
                # Add to available contracts if we had fetched from broker
                if removed_cd and self._available_contracts:
                    self._available_contracts.append(removed_cd)

        if removed_symbols:
            # Refresh tables
            self._load_current_contracts()
            self._populate_available_table()

            # Emit signal
            self.contracts_changed.emit()

            log.info(f"Removed {len(removed_symbols)} contracts from {self._asset.symbol}: {', '.join(removed_symbols)}")

    def get_asset(self) -> Asset:
        """Return the modified asset."""
        return self._asset

    # --------------------------------------------------------
    # WORKSPACE MANAGEMENT (for i3wm/Regolith)
    # --------------------------------------------------------

    def show(self) -> None:
        """Override show to move dialog to parent's workspace in i3wm."""
        super().show()

        # Schedule workspace move after dialog is fully shown
        if self._parent_window is not None:
            QTimer.singleShot(100, self._move_to_parent_workspace)

    def exec(self) -> int:
        """Override exec to move dialog to parent's workspace in i3wm."""
        # Schedule workspace move after dialog is shown
        if self._parent_window is not None:
            QTimer.singleShot(100, self._move_to_parent_workspace)
        return super().exec()

    def _move_to_parent_workspace(self) -> None:
        """Move this dialog to the same workspace as the parent window."""
        if self._parent_window is None:
            return

        parent_title = self._parent_window.windowTitle()
        parent_workspace = self._get_window_workspace(parent_title)
        if parent_workspace is not None:
            self._move_to_workspace(parent_workspace)

    def _get_window_workspace(self, window_title: str) -> Optional[int]:
        """Get the workspace number for a window by its title."""
        try:
            result = subprocess.run(
                ["i3-msg", "-t", "get_tree"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return None

            tree = json.loads(result.stdout)

            def find_workspace(node, current_workspace=None):
                # Track current workspace as we descend
                if node.get("type") == "workspace":
                    current_workspace = node.get("num")

                # Check if this node is our window
                title = node.get('window_properties', {}).get('title', '')
                if title == window_title:
                    return current_workspace

                # Recursively search children
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    found = find_workspace(child, current_workspace)
                    if found is not None:
                        return found
                return None

            return find_workspace(tree)
        except Exception as e:
            log.debug(f"Could not get workspace for window: {e}")
            return None

    def _get_this_dialog_con_id(self) -> Optional[int]:
        """Get the i3 container ID for this dialog."""
        try:
            result = subprocess.run(
                ["i3-msg", "-t", "get_tree"],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                return None

            tree = json.loads(result.stdout)
            dialog_title = self.windowTitle()

            def find_con_id(node):
                title = node.get('window_properties', {}).get('title', '')
                if title == dialog_title:
                    return node.get('id')
                for child in node.get('nodes', []) + node.get('floating_nodes', []):
                    found = find_con_id(child)
                    if found:
                        return found
                return None

            return find_con_id(tree)
        except Exception as e:
            log.debug(f"Could not get con_id for dialog: {e}")
            return None

    def _move_to_workspace(self, workspace: int) -> bool:
        """Move this dialog to the specified workspace using i3-msg."""
        try:
            con_id = self._get_this_dialog_con_id()
            if con_id is None:
                log.debug("Could not find con_id for this dialog")
                return False

            result = subprocess.run(
                ["i3-msg", f"[con_id={con_id}] move container to workspace number {workspace}"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                log.debug(f"Moved dialog to workspace {workspace}")
                return True
            else:
                log.debug(f"Failed to move dialog: {result.stderr}")
                return False
        except Exception as e:
            log.debug(f"Could not move dialog to workspace: {e}")
            return False
