"""
Stocks Watchlist View - MVVM implementation.

Migrated from the original StocksWatchlistPage to use the new
MVVM architecture with ViewModels and Commands.
"""

import logging
from typing import Optional

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel

from src.presentation.core.base_view import BaseView
from src.presentation.viewmodels.stocks_watchlist_viewmodel import StocksWatchlistViewModel

log = logging.getLogger("CellarLogger")


class StocksWatchlistView(BaseView):
    """
    MVVM-based Stocks Watchlist View.

    This view demonstrates the MVVM pattern with:
    - ViewModel binding for data
    - Command binding for actions
    - Signal connections for real-time updates

    The view is responsible only for UI - all business logic
    lives in the ViewModel.

    Example:
        # Create view with ViewModel from DI container
        vm = StocksWatchlistViewModel(
            watchlist_service=container.resolve(IWatchlistService),
            realtime_service=container.resolve(IRealtimeService),
            asset_service=container.resolve(IAssetService),
            market_data_bridge=container.resolve(MarketDataBridge),
        )
        view = StocksWatchlistView()
        view.set_view_model(vm)
        vm.load_watchlist()
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("stocks_watchlist_view")

        # Reference to detail window (kept open)
        self._detail_window: Optional[object] = None

        # Setup UI programmatically (or via .ui file)
        self._setup_ui()

        log.info("StocksWatchlistView initialized")

    def _setup_ui(self) -> None:
        """Setup the UI elements."""
        layout = QVBoxLayout(self)

        # Header with add stock controls
        header = QHBoxLayout()

        self.ticker_input = QLineEdit()
        self.ticker_input.setPlaceholderText("Enter ticker symbol...")
        self.ticker_input.setMaximumWidth(150)
        header.addWidget(self.ticker_input)

        self.add_button = QPushButton("Add Stock")
        header.addWidget(self.add_button)

        self.refresh_button = QPushButton("Refresh")
        header.addWidget(self.refresh_button)

        header.addStretch()

        self.status_label = QLabel("")
        header.addWidget(self.status_label)

        layout.addLayout(header)

        # Table area (placeholder - would use existing StockTable component)
        self.table_container = QVBoxLayout()
        layout.addLayout(self.table_container)

        # In a real implementation, we would add the StockTable here:
        # from src.ui.windows.main.pages.watchlists.stocks.table.table import StockTable
        # self.table = StockTable()
        # self.table_container.addWidget(self.table)

    def bind_view_model(self, vm: StocksWatchlistViewModel) -> None:
        """
        Bind ViewModel to View elements.

        This is where we connect:
        - Commands to buttons
        - Signals to update handlers
        - Observable properties to display elements
        """
        # Store reference
        self._vm = vm

        # Bind add button to command
        self.add_button.clicked.connect(self._on_add_clicked)

        # Bind refresh button to command
        self.refresh_button.clicked.connect(vm.refresh_command.execute)

        # Update button state based on command state
        vm.refresh_command.can_execute_changed.connect(
            self.refresh_button.setEnabled
        )

        # Handle property changes
        vm.property_changed.connect(self._on_property_changed)

        # Handle tick updates (for real-time data)
        vm.tick_updated.connect(self._on_tick_updated)

        # Handle errors
        vm.error_occurred.connect(self._on_error)

        # Handle busy state
        vm.is_busy_changed.connect(self._on_busy_changed)

        # Handle watchlist loaded
        vm.watchlist_loaded.connect(self._on_watchlist_loaded)

        # Handle symbol added/removed
        vm.symbol_added.connect(self._on_symbol_added)
        vm.symbol_removed.connect(self._on_symbol_removed)

        log.info("StocksWatchlistView bound to ViewModel")

    def _on_add_clicked(self) -> None:
        """Handle add button click."""
        symbol = self.ticker_input.text().strip()
        if symbol:
            self._vm.add_symbol(symbol)
            self.ticker_input.clear()

    @pyqtSlot(str, object)
    def _on_property_changed(self, name: str, value: object) -> None:
        """Handle ViewModel property changes."""
        if name == "symbols":
            self._update_symbols_display(value)
        elif name == "selected_symbol":
            self._update_selection(value)

    @pyqtSlot(str, object)
    def _on_tick_updated(self, symbol: str, tick_data: dict) -> None:
        """
        Handle real-time tick updates.

        The tick_data dict contains:
        - type: The tick type (bid, ask, last, etc.)
        - ticker: The symbol
        - price: The price value
        """
        # In a real implementation, forward to table model:
        # self.table.tableModel.on_update_model(tick_data)
        log.debug(f"Tick update: {symbol} - {tick_data.get('type')}: {tick_data.get('price')}")

    @pyqtSlot(str)
    def _on_error(self, message: str) -> None:
        """Handle errors from ViewModel."""
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: red;")
        log.error(f"ViewModel error: {message}")

    @pyqtSlot(bool)
    def _on_busy_changed(self, is_busy: bool) -> None:
        """Handle busy state changes."""
        self.add_button.setEnabled(not is_busy)
        self.refresh_button.setEnabled(not is_busy)
        if is_busy:
            self.status_label.setText("Loading...")
        else:
            self.status_label.setText("")

    @pyqtSlot(list)
    def _on_watchlist_loaded(self, symbols: list) -> None:
        """Handle watchlist loaded."""
        self.status_label.setText(f"Loaded {len(symbols)} symbols")
        self.status_label.setStyleSheet("color: green;")
        log.info(f"Watchlist loaded with {len(symbols)} symbols")

    @pyqtSlot(str)
    def _on_symbol_added(self, symbol: str) -> None:
        """Handle symbol added."""
        self.status_label.setText(f"Added {symbol}")
        self.status_label.setStyleSheet("color: green;")

    @pyqtSlot(str)
    def _on_symbol_removed(self, symbol: str) -> None:
        """Handle symbol removed."""
        self.status_label.setText(f"Removed {symbol}")
        self.status_label.setStyleSheet("color: orange;")

    def _update_symbols_display(self, symbols: list) -> None:
        """Update the UI to show current symbols."""
        # In a real implementation, sync with table
        pass

    def _update_selection(self, symbol: str) -> None:
        """Update UI to reflect selected symbol."""
        # In a real implementation, highlight selected row
        pass

    def onDestroy(self) -> None:
        """Clean up resources."""
        log.info("StocksWatchlistView destroying...")

        # Close detail window if open
        if self._detail_window is not None:
            self._detail_window.close()
            self._detail_window = None

        super().onDestroy()
