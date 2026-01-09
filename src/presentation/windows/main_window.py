"""
Main Window for FinanceApp using MVVM pattern.

This is the new main window that uses the refactored architecture
with dependency injection, MVVM pattern, and clean architecture.
"""

import logging
import sys
import threading
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, Optional, Tuple, Type
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QPushButton, QLineEdit, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QApplication, QStatusBar,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem,
)

from src.application.bootstrap import get_app
from src.presentation.core.base_view import BaseView
from src.presentation.core.base_window import BaseWindow
from src.presentation.viewmodels import StocksWatchlistViewModel, FuturesWatchlistViewModel, ETFWatchlistViewModel
from src.presentation.components.draggable_watchlist_table import DraggableWatchlistTable

log = logging.getLogger("CellarLogger")


class HomePage(BaseView):
    """Home page with navigation info."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("home_page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Welcome to FinanceApp")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("Use the menu to navigate:"))
        layout.addWidget(QLabel("  - File > Exit to close the application"))
        layout.addWidget(QLabel("  - Watchlists > Stocks for stock watchlist"))
        layout.addWidget(QLabel("  - Watchlists > Futures for futures watchlist"))
        layout.addWidget(QLabel("  - Watchlists > ETF for ETF watchlist"))
        layout.addWidget(QLabel("  - Assets > Stocks to manage stock assets"))
        layout.addWidget(QLabel("  - Assets > Futures to manage futures assets"))
        layout.addWidget(QLabel("  - Assets > ETF to manage ETF assets"))

        layout.addStretch()


class StocksWatchlistPage(BaseView):
    """Stocks Watchlist Page with multiple watchlists displayed as tabs."""

    # Loading spinner frames for animation
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Column indices for the watchlist table
    COL_VIEW = 0
    COL_SYMBOL = 1
    COL_BID_SIZE = 2
    COL_BID = 3
    COL_LAST = 4
    COL_ASK = 5
    COL_ASK_SIZE = 6
    COL_CHANGE = 7
    COL_OPEN = 8
    COL_HIGH = 9
    COL_LOW = 10
    COL_CLOSE = 11
    COL_VOLUME = 12
    COL_OPT_HIST_VOL = 13
    COL_OPT_IMPL_VOL = 14
    COL_DELETE = 15
    NUM_COLUMNS = 16

    COLUMN_HEADERS = [
        "", "Symbol", "Bid Size", "Bid", "Last", "Ask", "Ask Size",
        "Change %", "Open", "High", "Low", "Close",
        "Volume", "Hist Vol", "Impl Vol", ""
    ]

    @staticmethod
    def get_change_color(value: float) -> str:
        """Get background color based on percentage change value."""
        if value <= -25:
            return "#b71c1c"
        elif value > -25 and value <= -10:
            return "#d32f2f"
        elif value > -10 and value <= -6:
            return "#f44336"
        elif value > -6 and value <= -3:
            return "#e57373"
        elif value > -3 and value < 0:
            return "#ffcdd2"
        elif value == 0:
            return "white"
        elif value > 0 and value < 3:
            return "#c8e6c9"
        elif value >= 3 and value < 6:
            return "#81c784"
        elif value >= 6 and value < 10:
            return "#4caf50"
        elif value >= 10 and value < 25:
            return "#388e3c"
        elif value >= 25:
            return "#1b5e20"
        return "white"

    @staticmethod
    def is_dark_color(hex_color: str) -> bool:
        """Determine if a color is dark based on luminance."""
        # Handle named colors
        if hex_color.lower() == "white":
            return False

        # Remove # if present
        hex_color = hex_color.lstrip("#")

        # Convert hex to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Calculate relative luminance (ITU-R BT.709)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255

        # Return True if dark (luminance < 0.5)
        return luminance < 0.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("stocks_watchlist_page")
        self._vm = None
        self._tables = {}  # watchlist_id -> DraggableWatchlistTable
        self._detail_window = None  # Reference to prevent garbage collection
        self._spinner_frame = 0  # Current spinner animation frame
        self._spinner_timer = None  # Timer for spinner animation
        self._is_loading = False  # Loading state flag

        self._setup_ui()

        try:
            app = get_app()
            self._vm = StocksWatchlistViewModel(
                watchlist_service=app.watchlist_service,
                realtime_service=app.realtime_service,
                asset_service=app.asset_service,
                market_data_bridge=app.market_data_bridge,
            )
            self.set_view_model(self._vm)
            self._vm.load_all_watchlists()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            log.error(f"Failed to initialize StocksWatchlistPage: {e}")

    def _setup_ui(self) -> None:
        from src.presentation.components.watchlist_tab_widget import WatchlistTabWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QHBoxLayout()
        title = QLabel("Stocks Watchlist")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.ticker_input = QLineEdit()
        self.ticker_input.setObjectName("ticker_input")
        self.ticker_input.setPlaceholderText("Enter ticker...")
        self.ticker_input.setMaximumWidth(120)
        self.ticker_input.returnPressed.connect(self._on_add_clicked)
        header.addWidget(self.ticker_input)

        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("add_button")
        header.addWidget(self.add_button)

        # Loading spinner label (hidden by default)
        self.loading_label = QLabel("")
        self.loading_label.setObjectName("loading_label")
        self.loading_label.setStyleSheet("color: #2196F3; font-size: 14px; margin-left: 5px;")
        self.loading_label.setVisible(False)
        header.addWidget(self.loading_label)

        # Spinner timer for animation
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinner)

        self.add_from_assets_button = QPushButton("Add from Assets")
        self.add_from_assets_button.setObjectName("add_from_assets_button")
        self.add_from_assets_button.clicked.connect(self._on_add_from_assets)
        header.addWidget(self.add_from_assets_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("refresh_button")
        header.addWidget(self.refresh_button)

        layout.addLayout(header)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        layout.addWidget(self.status_label)

        # Tab widget for multiple watchlists
        self.tab_widget = WatchlistTabWidget()
        self.tab_widget.setObjectName("stocks_watchlist_tabs")
        self.tab_widget.watchlist_create_requested.connect(self._on_create_watchlist)
        self.tab_widget.watchlist_delete_requested.connect(self._on_delete_watchlist)
        self.tab_widget.watchlist_rename_requested.connect(self._on_rename_watchlist)
        self.tab_widget.watchlist_changed.connect(self._on_watchlist_tab_changed)
        layout.addWidget(self.tab_widget)

    def bind_view_model(self, vm: StocksWatchlistViewModel) -> None:
        self.add_button.clicked.connect(self._on_add_clicked)
        self.refresh_button.clicked.connect(lambda: vm.load_all_watchlists())

        # Multi-watchlist signals
        vm.watchlists_loaded.connect(self._on_watchlists_loaded)
        vm.watchlist_created.connect(self._on_watchlist_created)
        vm.watchlist_deleted.connect(self._on_watchlist_deleted)
        vm.active_watchlist_loaded.connect(self._on_active_watchlist_loaded)

        # Symbol signals
        vm.symbol_added.connect(self._on_symbol_added)
        vm.symbol_removed.connect(self._on_symbol_removed)
        vm.symbols_added.connect(self._on_symbols_added)
        vm.error_occurred.connect(self._on_error)
        vm.tick_updated.connect(self._on_tick_updated)

        # Asset creation signals
        vm.contracts_received.connect(self._on_contracts_received)
        vm.asset_created.connect(self._on_asset_created)
        vm.asset_creation_error.connect(self._on_asset_creation_error)
        vm.asset_creation_started.connect(self._on_asset_creation_started)

    def _create_table_widget(self, watchlist_id: str = "") -> DraggableWatchlistTable:
        """Create a new draggable table widget for a watchlist."""
        table = DraggableWatchlistTable(symbol_column=self.COL_SYMBOL)
        if watchlist_id:
            table.setObjectName(f"watchlist_table_{watchlist_id}")
        else:
            table.setObjectName("watchlist_table")
        table.setColumnCount(self.NUM_COLUMNS)
        table.setHorizontalHeaderLabels(self.COLUMN_HEADERS)

        # Set column resize modes
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # View column fixed small width (first column)
        header.setSectionResizeMode(self.COL_VIEW, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(self.COL_VIEW, 50)
        # Symbol column stretches
        header.setSectionResizeMode(self.COL_SYMBOL, QHeaderView.ResizeMode.Stretch)
        # Delete column fixed small width
        header.setSectionResizeMode(self.COL_DELETE, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(self.COL_DELETE, 30)

        table.setAlternatingRowColors(True)

        # Connect double-click to open detail window
        table.cellDoubleClicked.connect(self._on_watchlist_item_double_clicked)

        # Connect single-click for delete column
        table.cellClicked.connect(self._on_watchlist_cell_clicked)

        # Connect drag-drop order changed signal
        table.order_changed.connect(self._on_order_changed)

        return table

    def _on_watchlists_loaded(self, watchlists: list) -> None:
        """Handle watchlists loaded - create tabs for each."""
        self.tab_widget.clear_tabs()
        self._tables.clear()

        for wl in watchlists:
            wl_id = wl["id"]
            wl_name = wl.get("name", "Watchlist")

            table = self._create_table_widget(wl_id)
            self._tables[wl_id] = table
            self.tab_widget.add_watchlist_tab(wl_id, wl_name, table)

        # Set active tab
        if self._vm and self._vm.active_watchlist_id:
            self.tab_widget.set_active_watchlist(self._vm.active_watchlist_id)

        self.status_label.setText(f"Loaded {len(watchlists)} watchlists")

    def _on_watchlist_created(self, watchlist: dict) -> None:
        """Handle new watchlist created."""
        wl_id = watchlist["id"]
        wl_name = watchlist.get("name", "Watchlist")

        table = self._create_table_widget(wl_id)
        self._tables[wl_id] = table
        new_index = self.tab_widget.add_watchlist_tab(wl_id, wl_name, table)

        # Switch to the new watchlist using the returned index
        self.tab_widget.setCurrentIndex(new_index)
        if self._vm:
            self._vm.switch_watchlist(wl_id)

        self.status_label.setText(f"Created watchlist '{wl_name}'")

    def _on_watchlist_deleted(self, watchlist_id: str) -> None:
        """Handle watchlist deleted."""
        self.tab_widget.remove_watchlist_tab(watchlist_id)
        self._tables.pop(watchlist_id, None)
        self.status_label.setText("Watchlist deleted")

    def _on_watchlist_tab_changed(self, watchlist_id: str) -> None:
        """Handle tab selection change."""
        if self._vm:
            self._vm.switch_watchlist(watchlist_id)

    def _init_row(self, table: QTableWidget, row: int, symbol: str) -> None:
        """Initialize a row with default values, view button and delete button."""
        # Add view button (first column)
        view_btn = QPushButton("📈")
        view_btn.setObjectName(f"watchlist_view_{symbol.lower()}_button")
        view_btn.setToolTip(f"View chart for {symbol}")
        view_btn.setMaximumWidth(40)
        view_btn.clicked.connect(lambda checked, s=symbol: self._on_view_clicked(s))
        table.setCellWidget(row, self.COL_VIEW, view_btn)

        # Data columns
        table.setItem(row, self.COL_SYMBOL, QTableWidgetItem(symbol))
        table.setItem(row, self.COL_BID_SIZE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_BID, QTableWidgetItem("-"))
        table.setItem(row, self.COL_LAST, QTableWidgetItem("-"))
        table.setItem(row, self.COL_ASK, QTableWidgetItem("-"))
        table.setItem(row, self.COL_ASK_SIZE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_CHANGE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPEN, QTableWidgetItem("-"))
        table.setItem(row, self.COL_HIGH, QTableWidgetItem("-"))
        table.setItem(row, self.COL_LOW, QTableWidgetItem("-"))
        table.setItem(row, self.COL_CLOSE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_VOLUME, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPT_HIST_VOL, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPT_IMPL_VOL, QTableWidgetItem("-"))

        # Add delete item (last column) - flat text style matching futures watchlist
        delete_item = QTableWidgetItem("X")
        delete_item.setForeground(QColor("red"))
        font = delete_item.font()
        font.setBold(True)
        delete_item.setFont(font)
        delete_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, self.COL_DELETE, delete_item)

    def _on_delete_symbol(self, symbol: str) -> None:
        """Handle delete button click for a symbol."""
        if self._vm:
            self._vm.remove_symbol(symbol)

    def _on_order_changed(self, symbols: list) -> None:
        """Handle row order change from drag-drop."""
        if not self._vm:
            return

        # Persist new order via viewmodel
        self._vm.update_watchlist_order(symbols)

        # Recreate view buttons for all rows (they don't transfer during drag)
        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            self._recreate_view_buttons(table)

        self.status_label.setText("Watchlist order updated")
        log.debug(f"Stocks watchlist order changed: {symbols}")

    def _recreate_view_buttons(self, table: QTableWidget) -> None:
        """Recreate view buttons for all rows after drag-drop reorder."""
        for row in range(table.rowCount()):
            symbol_item = table.item(row, self.COL_SYMBOL)
            if not symbol_item:
                continue

            symbol = symbol_item.text()

            # Only recreate if button is missing
            if table.cellWidget(row, self.COL_VIEW) is None:
                view_btn = QPushButton("📈")
                view_btn.setObjectName(f"watchlist_view_{symbol.lower()}_button")
                view_btn.setToolTip(f"View chart for {symbol}")
                view_btn.setMaximumWidth(40)
                view_btn.clicked.connect(lambda checked, s=symbol: self._on_view_clicked(s))
                table.setCellWidget(row, self.COL_VIEW, view_btn)

    def _on_watchlist_cell_clicked(self, row: int, column: int) -> None:
        """Handle single-click on watchlist cell - check for delete column."""
        if column != self.COL_DELETE or not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        symbol_item = table.item(row, self.COL_SYMBOL)
        if symbol_item:
            self._on_delete_symbol(symbol_item.text())

    def _on_active_watchlist_loaded(self, symbols: list) -> None:
        """Handle symbols loaded for active watchlist."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        table.setRowCount(len(symbols))
        for i, symbol in enumerate(symbols):
            self._init_row(table, i, symbol)

        self.status_label.setText(f"Loaded {len(symbols)} symbols")

    def _on_create_watchlist(self) -> None:
        """Handle create watchlist button click."""
        from src.presentation.components.create_watchlist_dialog import CreateWatchlistDialog

        existing_names = self._vm.get_existing_watchlist_names() if self._vm else []
        name, accepted = CreateWatchlistDialog.get_watchlist_name(self, existing_names)

        if accepted and name and self._vm:
            self._vm.create_watchlist(name)

    def _on_delete_watchlist(self, watchlist_id: str) -> None:
        """Handle delete watchlist request."""
        reply = QMessageBox.question(
            self,
            "Delete Watchlist",
            "Are you sure you want to delete this watchlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self._vm:
            self._vm.delete_watchlist(watchlist_id)

    def _on_rename_watchlist(self, watchlist_id: str, new_name: str) -> None:
        """Handle rename watchlist request."""
        if self._vm:
            self._vm.rename_watchlist(watchlist_id, new_name)
            self.status_label.setText(f"Renamed watchlist to '{new_name}'")

    def _on_add_clicked(self) -> None:
        symbol = self.ticker_input.text().strip().upper()
        if not symbol or not self._vm:
            return

        self.ticker_input.clear()

        # Check if symbol is already in the watchlist
        if symbol in self._vm.symbols:
            self.status_label.setText(f"{symbol} is already in the watchlist")
            return

        # Check if asset exists in Assets collection
        if self._vm.asset_exists(symbol):
            # Asset exists, add directly to watchlist
            self._vm.add_symbol(symbol)
        else:
            # Asset doesn't exist - fetch from IB and create it
            self._vm.fetch_and_create_asset(symbol)

    def _on_add_from_assets(self) -> None:
        """Open dialog to add assets from saved assets."""
        from src.presentation.components.asset_selection_dialog import AssetSelectionDialog

        if not self._vm:
            return

        assets = self._vm.get_all_saved_assets()
        current_symbols = list(self._vm.symbols)

        selected, accepted = AssetSelectionDialog.select_assets(
            assets, current_symbols, self
        )

        if accepted and selected:
            count = self._vm.add_symbols(selected)
            self.status_label.setText(f"Added {count} symbols from assets")

    def _on_contracts_received(self, symbol: str, details_list: list) -> None:
        """Handle multiple contracts found - show selection dialog."""
        from src.presentation.components.contract_selection_dialog import ContractSelectionDialog

        self._stop_loading()

        selected_cd, accepted = ContractSelectionDialog.select_contract(
            symbol, details_list, self
        )

        if accepted and selected_cd:
            self._start_loading()
            self._vm.create_asset_from_selection(symbol, selected_cd)
        else:
            self.status_label.setText(f"Selection cancelled for {symbol}")

    def _on_asset_created(self, symbol: str) -> None:
        """Handle asset created signal."""
        self._stop_loading()
        self.status_label.setText(f"Asset {symbol} created from IB")

    def _on_asset_creation_error(self, symbol: str, error: str) -> None:
        """Handle asset creation error."""
        self._stop_loading()
        self.status_label.setText(f"Error adding {symbol}: {error}")

    def _on_asset_creation_started(self, symbol: str) -> None:
        """Handle asset creation started - show loading status."""
        self.status_label.setText(f"Searching IB for {symbol}...")
        self._start_loading()

    def _start_loading(self) -> None:
        """Start the loading spinner animation."""
        self._is_loading = True
        self._spinner_frame = 0
        self.loading_label.setVisible(True)
        self.loading_label.setText(self.SPINNER_FRAMES[0] + " Searching...")
        self.add_button.setEnabled(False)
        self.ticker_input.setEnabled(False)
        self._spinner_timer.start(80)  # 80ms per frame for smooth animation

    def _stop_loading(self) -> None:
        """Stop the loading spinner animation."""
        self._is_loading = False
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.loading_label.setText("")
        self.add_button.setEnabled(True)
        self.ticker_input.setEnabled(True)

    def _update_spinner(self) -> None:
        """Update the spinner animation frame."""
        if not self._is_loading:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        self.loading_label.setText(self.SPINNER_FRAMES[self._spinner_frame] + " Searching...")

    def _on_symbol_added(self, symbol: str) -> None:
        if not self._vm:
            return

        self._stop_loading()
        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            row = table.rowCount()
            table.insertRow(row)
            self._init_row(table, row, symbol)
        self.status_label.setText(f"Added {symbol}")

    def _on_symbols_added(self, symbols: list) -> None:
        self.status_label.setText(f"Added {len(symbols)} symbols")

    def _on_symbol_removed(self, symbol: str) -> None:
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            for row in range(table.rowCount()):
                item = table.item(row, self.COL_SYMBOL)
                if item and item.text() == symbol:
                    table.removeRow(row)
                    break
        self.status_label.setText(f"Removed {symbol}")

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _format_number(self, value: float, decimals: int = 2) -> str:
        """Format a number for display, handling zero/None values."""
        if value is None or value == 0:
            return "-"
        return f"{value:,.{decimals}f}"

    def _format_volume(self, value: int) -> str:
        """Format volume with K/M suffix."""
        if value is None or value == 0:
            return "-"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(value)

    def _format_percent(self, value: float) -> str:
        """Format percentage value."""
        if value is None or value == 0:
            return "-"
        return f"{value:+.2f}%"

    def _on_tick_updated(self, symbol: str, tick_data: dict) -> None:
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        for row in range(table.rowCount()):
            item = table.item(row, self.COL_SYMBOL)
            if item and item.text() == symbol:
                # Update bid/ask with sizes
                if "bid_size" in tick_data and tick_data["bid_size"]:
                    table.setItem(row, self.COL_BID_SIZE, QTableWidgetItem(str(tick_data["bid_size"])))
                if "bid" in tick_data and tick_data["bid"]:
                    table.setItem(row, self.COL_BID, QTableWidgetItem(self._format_number(tick_data["bid"])))
                if "last" in tick_data and tick_data["last"]:
                    last_item = QTableWidgetItem(self._format_number(tick_data["last"]))
                    # Highlight the Last column to make it stand out
                    font = last_item.font()
                    font.setBold(True)
                    last_item.setFont(font)
                    last_item.setBackground(QColor("#e3f2fd"))  # Light blue background
                    last_item.setForeground(QColor("black"))    # Black text for prominence
                    table.setItem(row, self.COL_LAST, last_item)
                if "ask" in tick_data and tick_data["ask"]:
                    table.setItem(row, self.COL_ASK, QTableWidgetItem(self._format_number(tick_data["ask"])))
                if "ask_size" in tick_data and tick_data["ask_size"]:
                    table.setItem(row, self.COL_ASK_SIZE, QTableWidgetItem(str(tick_data["ask_size"])))

                # OHLC data
                if "open" in tick_data and tick_data["open"]:
                    table.setItem(row, self.COL_OPEN, QTableWidgetItem(self._format_number(tick_data["open"])))
                if "high" in tick_data and tick_data["high"]:
                    table.setItem(row, self.COL_HIGH, QTableWidgetItem(self._format_number(tick_data["high"])))
                if "low" in tick_data and tick_data["low"]:
                    table.setItem(row, self.COL_LOW, QTableWidgetItem(self._format_number(tick_data["low"])))
                if "close" in tick_data and tick_data["close"]:
                    table.setItem(row, self.COL_CLOSE, QTableWidgetItem(self._format_number(tick_data["close"])))

                # Calculate and display change with color
                last_price = tick_data.get("last", 0)
                close_price = tick_data.get("close", 0)
                if last_price and close_price:
                    change_pct = ((last_price - close_price) / close_price) * 100
                    change_item = QTableWidgetItem(self._format_percent(change_pct))
                    bg_color = self.get_change_color(change_pct)
                    change_item.setBackground(QColor(bg_color))
                    # Set text color based on background luminance
                    text_color = "white" if self.is_dark_color(bg_color) else "black"
                    change_item.setForeground(QColor(text_color))
                    table.setItem(row, self.COL_CHANGE, change_item)

                # Volume
                if "volume" in tick_data and tick_data["volume"]:
                    table.setItem(row, self.COL_VOLUME, QTableWidgetItem(self._format_volume(tick_data["volume"])))

                # Option volatilities (if available) - IB sends as decimal (0.25 = 25%)
                if "option_historical_vol" in tick_data and tick_data["option_historical_vol"]:
                    hv = tick_data["option_historical_vol"]
                    # IB sends as decimal, convert to percentage
                    hv_pct = hv * 100 if hv < 1 else hv
                    table.setItem(row, self.COL_OPT_HIST_VOL, QTableWidgetItem(f"{hv_pct:.1f}%"))
                if "option_implied_vol" in tick_data and tick_data["option_implied_vol"]:
                    iv = tick_data["option_implied_vol"]
                    # IB sends as decimal, convert to percentage
                    iv_pct = iv * 100 if iv < 1 else iv
                    table.setItem(row, self.COL_OPT_IMPL_VOL, QTableWidgetItem(f"{iv_pct:.1f}%"))

                break

    def _on_watchlist_item_double_clicked(self, row: int, column: int) -> None:
        """Handle double-click on watchlist row - open detail window."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        symbol_item = table.item(row, self.COL_SYMBOL)
        if not symbol_item:
            return

        symbol = symbol_item.text()
        self._open_detail_window(symbol)

    def _on_view_clicked(self, symbol: str) -> None:
        """Handle view button click - open detail window."""
        self._open_detail_window(symbol)

    def _open_detail_window(self, symbol: str) -> None:
        """Open the asset detail window for the given symbol."""
        try:
            app = get_app()
            asset = app.asset_service.get_asset("STOCK", symbol)
            if asset:
                from src.presentation.windows.asset_detail import AssetDetailWindow
                self._detail_window = AssetDetailWindow(asset, parent=self.window())
                self._detail_window.show()
                self.status_label.setText(f"Opened detail for {symbol}")
            else:
                self.status_label.setText(f"Asset {symbol} not found in saved assets")
        except Exception as e:
            self.status_label.setText(f"Error opening detail: {e}")
            log.error(f"Error opening asset detail: {e}")
            import traceback
            traceback.print_exc()

    def onDestroy(self) -> None:
        if self._vm:
            self._vm.dispose()
        if self._detail_window:
            self._detail_window.close()
            self._detail_window = None
        super().onDestroy()


class FuturesWatchlistPage(BaseView):
    """Futures Watchlist Page with hierarchical tree view showing symbols and contracts."""

    # Loading spinner frames for animation
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("futures_watchlist_page")
        self._vm = None
        # watchlist_id -> (QTreeView, FuturesTreeModel)
        self._tree_views: Dict[str, tuple] = {}
        self._detail_window = None  # Reference to prevent garbage collection
        self._spinner_frame = 0  # Current spinner animation frame
        self._spinner_timer = None  # Timer for spinner animation
        self._is_loading = False  # Loading state flag

        self._setup_ui()

        try:
            app = get_app()
            self._vm = FuturesWatchlistViewModel(
                watchlist_service=app.watchlist_service,
                realtime_service=app.realtime_service,
                asset_service=app.asset_service,
                market_data_bridge=app.market_data_bridge,
            )
            self.set_view_model(self._vm)
            self._vm.load_all_watchlists()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            log.error(f"Failed to initialize FuturesWatchlistPage: {e}")

    def _setup_ui(self) -> None:
        from src.presentation.components.watchlist_tab_widget import WatchlistTabWidget
        from PyQt6.QtWidgets import QTreeView

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QHBoxLayout()
        title = QLabel("Futures Watchlist")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.ticker_input = QLineEdit()
        self.ticker_input.setObjectName("futures_ticker_input")
        self.ticker_input.setPlaceholderText("Enter symbol...")
        self.ticker_input.setMaximumWidth(120)
        self.ticker_input.returnPressed.connect(self._on_add_clicked)
        header.addWidget(self.ticker_input)

        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("futures_add_button")
        header.addWidget(self.add_button)

        # Loading spinner label (hidden by default)
        self.loading_label = QLabel("")
        self.loading_label.setObjectName("futures_loading_label")
        self.loading_label.setStyleSheet("color: #2196F3; font-size: 14px; margin-left: 5px;")
        self.loading_label.setVisible(False)
        header.addWidget(self.loading_label)

        # Spinner timer for animation
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinner)

        self.add_from_assets_button = QPushButton("Add from Assets")
        self.add_from_assets_button.setObjectName("futures_add_from_assets_button")
        self.add_from_assets_button.clicked.connect(self._on_add_from_assets)
        header.addWidget(self.add_from_assets_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("futures_refresh_button")
        header.addWidget(self.refresh_button)

        layout.addLayout(header)

        self.status_label = QLabel("")
        self.status_label.setObjectName("futures_status_label")
        layout.addWidget(self.status_label)

        # Tab widget for multiple watchlists
        self.tab_widget = WatchlistTabWidget()
        self.tab_widget.setObjectName("futures_watchlist_tabs")
        self.tab_widget.watchlist_create_requested.connect(self._on_create_watchlist)
        self.tab_widget.watchlist_delete_requested.connect(self._on_delete_watchlist)
        self.tab_widget.watchlist_rename_requested.connect(self._on_rename_watchlist)
        self.tab_widget.watchlist_changed.connect(self._on_watchlist_tab_changed)
        layout.addWidget(self.tab_widget)

    def bind_view_model(self, vm: FuturesWatchlistViewModel) -> None:
        self.add_button.clicked.connect(self._on_add_clicked)
        self.refresh_button.clicked.connect(lambda: vm.load_all_watchlists())

        # Multi-watchlist signals
        vm.watchlists_loaded.connect(self._on_watchlists_loaded)
        vm.watchlist_created.connect(self._on_watchlist_created)
        vm.watchlist_deleted.connect(self._on_watchlist_deleted)
        vm.active_watchlist_loaded.connect(self._on_active_watchlist_loaded)

        # Symbol signals
        vm.symbol_added.connect(self._on_symbol_added)
        vm.symbol_removed.connect(self._on_symbol_removed)
        vm.symbols_added.connect(self._on_symbols_added)
        vm.error_occurred.connect(self._on_error)
        vm.tick_updated.connect(self._on_tick_updated)

        # Asset creation signals
        vm.contracts_received.connect(self._on_contracts_received)
        vm.asset_created.connect(self._on_asset_created)
        vm.asset_creation_error.connect(self._on_asset_creation_error)
        vm.asset_creation_started.connect(self._on_asset_creation_started)

    def _create_tree_view(self, watchlist_id: str = "") -> tuple:
        """Create a new tree view with model for a watchlist.

        Returns:
            Tuple of (QTreeView, FuturesTreeModel)
        """
        from PyQt6.QtWidgets import QTreeView, QAbstractItemView
        from src.presentation.models import FuturesTreeModel

        tree_view = QTreeView()
        if watchlist_id:
            tree_view.setObjectName(f"futures_watchlist_tree_{watchlist_id}")
        else:
            tree_view.setObjectName("futures_watchlist_tree")

        model = FuturesTreeModel(tree_view)
        tree_view.setModel(model)

        # Configure tree view
        tree_view.setAlternatingRowColors(True)
        tree_view.setSelectionBehavior(QTreeView.SelectionBehavior.SelectRows)
        tree_view.setUniformRowHeights(True)
        tree_view.setAnimated(True)
        tree_view.setIndentation(20)  # Control expand arrow indentation

        # Enable drag-drop for parent item reordering
        tree_view.setDragEnabled(True)
        tree_view.setAcceptDrops(True)
        tree_view.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        tree_view.setDropIndicatorShown(True)
        tree_view.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Configure header
        header = tree_view.header()
        header.setStretchLastSection(False)

        # View column - fixed width (needs space for expand arrow + icon)
        header.setSectionResizeMode(model.COL_VIEW, QHeaderView.ResizeMode.Fixed)
        tree_view.setColumnWidth(model.COL_VIEW, 60)

        # Symbol column should stretch
        header.setSectionResizeMode(model.COL_SYMBOL, QHeaderView.ResizeMode.Stretch)

        # Other data columns resize to content
        for i in range(model.COL_MONTH, model.COL_DELETE):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Delete column - fixed small width
        header.setSectionResizeMode(model.COL_DELETE, QHeaderView.ResizeMode.Fixed)
        tree_view.setColumnWidth(model.COL_DELETE, 30)

        # Connect click to handle View/Delete columns
        tree_view.clicked.connect(self._on_tree_item_clicked)
        # Connect double-click to open detail window
        tree_view.doubleClicked.connect(self._on_tree_item_double_clicked)
        # Connect expanded/collapsed to hide/show data in parent rows
        tree_view.expanded.connect(lambda idx: model.set_item_expanded(idx, True))
        tree_view.collapsed.connect(lambda idx: model.set_item_expanded(idx, False))

        # Connect order changed signal for drag-drop reordering
        model.order_changed.connect(self._on_futures_order_changed)

        return (tree_view, model)

    def _on_watchlists_loaded(self, watchlists: list) -> None:
        """Handle watchlists loaded - create tabs for each."""
        self.tab_widget.clear_tabs()
        self._tree_views.clear()

        for wl in watchlists:
            wl_id = wl["id"]
            wl_name = wl.get("name", "Watchlist")

            tree_view, model = self._create_tree_view(wl_id)
            self._tree_views[wl_id] = (tree_view, model)
            self.tab_widget.add_watchlist_tab(wl_id, wl_name, tree_view)

        # Set active tab
        if self._vm and self._vm.active_watchlist_id:
            self.tab_widget.set_active_watchlist(self._vm.active_watchlist_id)

        self.status_label.setText(f"Loaded {len(watchlists)} watchlists")

    def _on_watchlist_created(self, watchlist: dict) -> None:
        """Handle new watchlist created."""
        wl_id = watchlist["id"]
        wl_name = watchlist.get("name", "Watchlist")

        tree_view, model = self._create_tree_view(wl_id)
        self._tree_views[wl_id] = (tree_view, model)
        new_index = self.tab_widget.add_watchlist_tab(wl_id, wl_name, tree_view)

        # Switch to the new watchlist using the returned index
        self.tab_widget.setCurrentIndex(new_index)
        if self._vm:
            self._vm.switch_watchlist(wl_id)

        self.status_label.setText(f"Created watchlist '{wl_name}'")

    def _on_watchlist_deleted(self, watchlist_id: str) -> None:
        """Handle watchlist deleted."""
        self.tab_widget.remove_watchlist_tab(watchlist_id)
        self._tree_views.pop(watchlist_id, None)
        self.status_label.setText("Watchlist deleted")

    def _on_watchlist_tab_changed(self, watchlist_id: str) -> None:
        """Handle tab selection change."""
        if self._vm:
            self._vm.switch_watchlist(watchlist_id)

    def _on_active_watchlist_loaded(self, symbols: list) -> None:
        """Handle symbols loaded for active watchlist."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if not tree_data:
            return

        tree_view, model = tree_data

        # Load assets into the model
        model.load_assets(self._vm.assets)

        # Expand all parent items by default
        tree_view.expandAll()

        # Count total contracts
        total_contracts = sum(
            len(asset.contract_details)
            for asset in self._vm.assets.values()
        )
        self.status_label.setText(
            f"Loaded {len(symbols)} futures with {total_contracts} contracts"
        )

    def _on_create_watchlist(self) -> None:
        """Handle create watchlist button click."""
        from src.presentation.components.create_watchlist_dialog import CreateWatchlistDialog

        existing_names = self._vm.get_existing_watchlist_names() if self._vm else []
        name, accepted = CreateWatchlistDialog.get_watchlist_name(self, existing_names)

        if accepted and name and self._vm:
            self._vm.create_watchlist(name)

    def _on_delete_watchlist(self, watchlist_id: str) -> None:
        """Handle delete watchlist request."""
        reply = QMessageBox.question(
            self,
            "Delete Watchlist",
            "Are you sure you want to delete this watchlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self._vm:
            self._vm.delete_watchlist(watchlist_id)

    def _on_rename_watchlist(self, watchlist_id: str, new_name: str) -> None:
        """Handle rename watchlist request."""
        if self._vm:
            self._vm.rename_watchlist(watchlist_id, new_name)
            self.status_label.setText(f"Renamed watchlist to '{new_name}'")

    def _on_add_clicked(self) -> None:
        symbol = self.ticker_input.text().strip().upper()
        if not symbol or not self._vm:
            return

        self.ticker_input.clear()

        # Check if symbol is already in the watchlist
        if symbol in self._vm.symbols:
            self.status_label.setText(f"{symbol} is already in the watchlist")
            return

        # Check if asset exists in Assets collection
        if self._vm.asset_exists(symbol):
            # Asset exists, add directly to watchlist
            self._vm.add_symbol(symbol)
        else:
            # Asset doesn't exist - fetch from IB and create it
            self._vm.fetch_and_create_asset(symbol)

    def _on_add_from_assets(self) -> None:
        """Open dialog to add assets from saved assets."""
        from src.presentation.components.asset_selection_dialog import AssetSelectionDialog

        if not self._vm:
            return

        assets = self._vm.get_all_saved_assets()
        current_symbols = list(self._vm.symbols)

        selected, accepted = AssetSelectionDialog.select_assets(
            assets, current_symbols, self
        )

        if accepted and selected:
            count = self._vm.add_symbols(selected)
            self.status_label.setText(f"Added {count} symbols from assets")

    def _on_contracts_received(self, symbol: str, details_list: list) -> None:
        """Handle multiple contracts found - show selection dialog."""
        from src.presentation.components.contract_selection_dialog import ContractSelectionDialog

        self._stop_loading()

        selected_cd, accepted = ContractSelectionDialog.select_contract(
            symbol, details_list, self
        )

        if accepted and selected_cd:
            self._start_loading()
            self._vm.create_asset_from_selection(symbol, selected_cd)
        else:
            self.status_label.setText(f"Selection cancelled for {symbol}")

    def _on_asset_created(self, symbol: str) -> None:
        """Handle asset created signal."""
        self._stop_loading()
        self.status_label.setText(f"Asset {symbol} created from IB")

    def _on_asset_creation_error(self, symbol: str, error: str) -> None:
        """Handle asset creation error."""
        self._stop_loading()
        self.status_label.setText(f"Error adding {symbol}: {error}")

    def _on_asset_creation_started(self, symbol: str) -> None:
        """Handle asset creation started - show loading status."""
        self.status_label.setText(f"Searching IB for {symbol}...")
        self._start_loading()

    def _start_loading(self) -> None:
        """Start the loading spinner animation."""
        self._is_loading = True
        self._spinner_frame = 0
        self.loading_label.setVisible(True)
        self.loading_label.setText(self.SPINNER_FRAMES[0] + " Searching...")
        self.add_button.setEnabled(False)
        self.ticker_input.setEnabled(False)
        self._spinner_timer.start(80)  # 80ms per frame for smooth animation

    def _stop_loading(self) -> None:
        """Stop the loading spinner animation."""
        self._is_loading = False
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.loading_label.setText("")
        self.add_button.setEnabled(True)
        self.ticker_input.setEnabled(True)

    def _update_spinner(self) -> None:
        """Update the spinner animation frame."""
        if not self._is_loading:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        self.loading_label.setText(self.SPINNER_FRAMES[self._spinner_frame] + " Searching...")

    def _on_symbol_added(self, symbol: str) -> None:
        if not self._vm:
            return

        self._stop_loading()
        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if tree_data:
            tree_view, model = tree_data
            asset = self._vm.get_asset(symbol)
            if asset:
                model.add_symbol(symbol, asset)
                # Expand the new item
                tree_view.expandAll()
        self.status_label.setText(f"Added {symbol}")

    def _on_symbols_added(self, symbols: list) -> None:
        """Handle multiple symbols added - reload the model."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if tree_data:
            tree_view, model = tree_data
            model.load_assets(self._vm.assets)
            tree_view.expandAll()
        self.status_label.setText(f"Added {len(symbols)} symbols")

    def _on_symbol_removed(self, symbol: str) -> None:
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if tree_data:
            _, model = tree_data
            model.remove_symbol(symbol)
        self.status_label.setText(f"Removed {symbol}")

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _on_tick_updated(self, symbol: str, local_symbol: str, tick_data: dict) -> None:
        """Handle tick update - forward to the tree model."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if not tree_data:
            return

        _, model = tree_data
        model.update_tick(symbol, local_symbol, tick_data)

    def _on_tree_item_clicked(self, index) -> None:
        """Handle click on tree item - check for View/Delete columns."""
        if not self._vm or not index.isValid():
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if not tree_data:
            return

        _, model = tree_data
        item = model.get_item_at_index(index)
        if not item:
            return

        col = index.column()

        # Handle View column click
        if col == model.COL_VIEW:
            self._open_detail_window(item.symbol)

        # Handle Delete column click (only for parent items)
        elif col == model.COL_DELETE and item.is_parent:
            reply = QMessageBox.question(
                self,
                "Remove Symbol",
                f"Remove {item.symbol} from watchlist?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._vm.remove_symbol(item.symbol)

    def _on_futures_order_changed(self, symbols: list) -> None:
        """Handle parent item order change from drag-drop."""
        if not self._vm:
            return

        # Persist new order via viewmodel
        self._vm.update_watchlist_order(symbols)
        self.status_label.setText("Futures watchlist order updated")
        log.debug(f"Futures watchlist order changed: {symbols}")

    def _on_tree_item_double_clicked(self, index) -> None:
        """Handle double-click on tree item - open detail window."""
        if not self._vm or not index.isValid():
            return

        active_id = self._vm.active_watchlist_id
        tree_data = self._tree_views.get(active_id)
        if not tree_data:
            return

        _, model = tree_data
        item = model.get_item_at_index(index)
        if item:
            self._open_detail_window(item.symbol)

    def _open_detail_window(self, symbol: str) -> None:
        """Open the asset detail window for the given symbol."""
        try:
            app = get_app()
            asset = app.asset_service.get_asset("FUTURE", symbol)
            if asset:
                from src.presentation.windows.asset_detail import AssetDetailWindow
                self._detail_window = AssetDetailWindow(asset, parent=self.window())
                self._detail_window.show()
                self.status_label.setText(f"Opened detail for {symbol}")
            else:
                self.status_label.setText(f"Asset {symbol} not found in saved assets")
        except Exception as e:
            self.status_label.setText(f"Error opening detail: {e}")
            log.error(f"Error opening asset detail: {e}")
            import traceback
            traceback.print_exc()

    def onDestroy(self) -> None:
        if self._vm:
            self._vm.dispose()
        if self._detail_window:
            self._detail_window.close()
            self._detail_window = None
        super().onDestroy()


class ETFWatchlistPage(BaseView):
    """ETF Watchlist Page with multiple watchlists displayed as tabs."""

    # Loading spinner frames for animation
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Column indices for the watchlist table (same as stocks)
    COL_VIEW = 0
    COL_SYMBOL = 1
    COL_BID_SIZE = 2
    COL_BID = 3
    COL_LAST = 4
    COL_ASK = 5
    COL_ASK_SIZE = 6
    COL_CHANGE = 7
    COL_OPEN = 8
    COL_HIGH = 9
    COL_LOW = 10
    COL_CLOSE = 11
    COL_VOLUME = 12
    COL_OPT_HIST_VOL = 13
    COL_OPT_IMPL_VOL = 14
    COL_DELETE = 15
    NUM_COLUMNS = 16

    COLUMN_HEADERS = [
        "", "Symbol", "Bid Size", "Bid", "Last", "Ask", "Ask Size",
        "Change %", "Open", "High", "Low", "Close",
        "Volume", "Hist Vol", "Impl Vol", ""
    ]

    @staticmethod
    def get_change_color(value: float) -> str:
        """Get background color based on percentage change value."""
        if value <= -25:
            return "#b71c1c"
        elif value > -25 and value <= -10:
            return "#d32f2f"
        elif value > -10 and value <= -6:
            return "#f44336"
        elif value > -6 and value <= -3:
            return "#e57373"
        elif value > -3 and value < 0:
            return "#ffcdd2"
        elif value == 0:
            return "white"
        elif value > 0 and value < 3:
            return "#c8e6c9"
        elif value >= 3 and value < 6:
            return "#81c784"
        elif value >= 6 and value < 10:
            return "#4caf50"
        elif value >= 10 and value < 25:
            return "#388e3c"
        elif value >= 25:
            return "#1b5e20"
        return "white"

    @staticmethod
    def is_dark_color(hex_color: str) -> bool:
        """Determine if a color is dark based on luminance."""
        if hex_color.lower() == "white":
            return False
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return luminance < 0.5

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setObjectName("etf_watchlist_page")
        self._vm = None
        self._tables = {}  # watchlist_id -> DraggableWatchlistTable
        self._detail_window = None
        self._spinner_frame = 0  # Current spinner animation frame
        self._spinner_timer = None  # Timer for spinner animation
        self._is_loading = False  # Loading state flag

        self._setup_ui()

        try:
            app = get_app()
            self._vm = ETFWatchlistViewModel(
                watchlist_service=app.watchlist_service,
                realtime_service=app.realtime_service,
                asset_service=app.asset_service,
                market_data_bridge=app.market_data_bridge,
            )
            self.set_view_model(self._vm)
            self._vm.load_all_watchlists()
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            log.error(f"Failed to initialize ETFWatchlistPage: {e}")

    def _setup_ui(self) -> None:
        from src.presentation.components.watchlist_tab_widget import WatchlistTabWidget

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QHBoxLayout()
        title = QLabel("ETF Watchlist")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.ticker_input = QLineEdit()
        self.ticker_input.setObjectName("etf_ticker_input")
        self.ticker_input.setPlaceholderText("Enter ticker...")
        self.ticker_input.setMaximumWidth(120)
        self.ticker_input.returnPressed.connect(self._on_add_clicked)
        header.addWidget(self.ticker_input)

        self.add_button = QPushButton("Add")
        self.add_button.setObjectName("etf_add_button")
        header.addWidget(self.add_button)

        # Loading spinner label (hidden by default)
        self.loading_label = QLabel("")
        self.loading_label.setObjectName("etf_loading_label")
        self.loading_label.setStyleSheet("color: #2196F3; font-size: 14px; margin-left: 5px;")
        self.loading_label.setVisible(False)
        header.addWidget(self.loading_label)

        # Spinner timer for animation
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinner)

        self.add_from_assets_button = QPushButton("Add from Assets")
        self.add_from_assets_button.setObjectName("etf_add_from_assets_button")
        self.add_from_assets_button.clicked.connect(self._on_add_from_assets)
        header.addWidget(self.add_from_assets_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName("etf_refresh_button")
        header.addWidget(self.refresh_button)

        layout.addLayout(header)

        # Status
        self.status_label = QLabel("")
        self.status_label.setObjectName("etf_status_label")
        layout.addWidget(self.status_label)

        # Tab widget for multiple watchlists
        self.tab_widget = WatchlistTabWidget()
        self.tab_widget.setObjectName("etf_watchlist_tabs")
        self.tab_widget.watchlist_create_requested.connect(self._on_create_watchlist)
        self.tab_widget.watchlist_delete_requested.connect(self._on_delete_watchlist)
        self.tab_widget.watchlist_rename_requested.connect(self._on_rename_watchlist)
        self.tab_widget.watchlist_changed.connect(self._on_watchlist_tab_changed)
        layout.addWidget(self.tab_widget)

    def bind_view_model(self, vm: ETFWatchlistViewModel) -> None:
        self.add_button.clicked.connect(self._on_add_clicked)
        self.refresh_button.clicked.connect(lambda: vm.load_all_watchlists())

        # Multi-watchlist signals
        vm.watchlists_loaded.connect(self._on_watchlists_loaded)
        vm.watchlist_created.connect(self._on_watchlist_created)
        vm.watchlist_deleted.connect(self._on_watchlist_deleted)
        vm.active_watchlist_loaded.connect(self._on_active_watchlist_loaded)

        # Symbol signals
        vm.symbol_added.connect(self._on_symbol_added)
        vm.symbol_removed.connect(self._on_symbol_removed)
        vm.symbols_added.connect(self._on_symbols_added)
        vm.error_occurred.connect(self._on_error)
        vm.tick_updated.connect(self._on_tick_updated)

        # Asset creation signals
        vm.contracts_received.connect(self._on_contracts_received)
        vm.asset_created.connect(self._on_asset_created)
        vm.asset_creation_error.connect(self._on_asset_creation_error)
        vm.asset_creation_started.connect(self._on_asset_creation_started)

    def _create_table_widget(self, watchlist_id: str = "") -> DraggableWatchlistTable:
        """Create a new draggable table widget for a watchlist."""
        table = DraggableWatchlistTable(symbol_column=self.COL_SYMBOL)
        if watchlist_id:
            table.setObjectName(f"etf_watchlist_table_{watchlist_id}")
        else:
            table.setObjectName("etf_watchlist_table")
        table.setColumnCount(self.NUM_COLUMNS)
        table.setHorizontalHeaderLabels(self.COLUMN_HEADERS)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_VIEW, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(self.COL_VIEW, 50)
        header.setSectionResizeMode(self.COL_SYMBOL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_DELETE, QHeaderView.ResizeMode.Fixed)
        table.setColumnWidth(self.COL_DELETE, 30)

        table.setAlternatingRowColors(True)
        table.cellDoubleClicked.connect(self._on_watchlist_item_double_clicked)
        table.cellClicked.connect(self._on_watchlist_cell_clicked)

        # Connect drag-drop order changed signal
        table.order_changed.connect(self._on_order_changed)

        return table

    def _on_watchlists_loaded(self, watchlists: list) -> None:
        """Handle watchlists loaded - create tabs for each."""
        self.tab_widget.clear_tabs()
        self._tables.clear()

        for wl in watchlists:
            wl_id = wl["id"]
            wl_name = wl.get("name", "Watchlist")

            table = self._create_table_widget(wl_id)
            self._tables[wl_id] = table
            self.tab_widget.add_watchlist_tab(wl_id, wl_name, table)

        if self._vm and self._vm.active_watchlist_id:
            self.tab_widget.set_active_watchlist(self._vm.active_watchlist_id)

        self.status_label.setText(f"Loaded {len(watchlists)} watchlists")

    def _on_watchlist_created(self, watchlist: dict) -> None:
        """Handle new watchlist created."""
        wl_id = watchlist["id"]
        wl_name = watchlist.get("name", "Watchlist")

        table = self._create_table_widget(wl_id)
        self._tables[wl_id] = table
        new_index = self.tab_widget.add_watchlist_tab(wl_id, wl_name, table)

        self.tab_widget.setCurrentIndex(new_index)
        if self._vm:
            self._vm.switch_watchlist(wl_id)

        self.status_label.setText(f"Created watchlist '{wl_name}'")

    def _on_watchlist_deleted(self, watchlist_id: str) -> None:
        """Handle watchlist deleted."""
        self.tab_widget.remove_watchlist_tab(watchlist_id)
        self._tables.pop(watchlist_id, None)
        self.status_label.setText("Watchlist deleted")

    def _on_watchlist_tab_changed(self, watchlist_id: str) -> None:
        """Handle tab selection change."""
        if self._vm:
            self._vm.switch_watchlist(watchlist_id)

    def _init_row(self, table: QTableWidget, row: int, symbol: str) -> None:
        """Initialize a row with default values, view button and delete button."""
        view_btn = QPushButton("📈")
        view_btn.setObjectName(f"etf_watchlist_view_{symbol.lower()}_button")
        view_btn.setToolTip(f"View chart for {symbol}")
        view_btn.setMaximumWidth(40)
        view_btn.clicked.connect(lambda checked, s=symbol: self._on_view_clicked(s))
        table.setCellWidget(row, self.COL_VIEW, view_btn)

        table.setItem(row, self.COL_SYMBOL, QTableWidgetItem(symbol))
        table.setItem(row, self.COL_BID_SIZE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_BID, QTableWidgetItem("-"))
        table.setItem(row, self.COL_LAST, QTableWidgetItem("-"))
        table.setItem(row, self.COL_ASK, QTableWidgetItem("-"))
        table.setItem(row, self.COL_ASK_SIZE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_CHANGE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPEN, QTableWidgetItem("-"))
        table.setItem(row, self.COL_HIGH, QTableWidgetItem("-"))
        table.setItem(row, self.COL_LOW, QTableWidgetItem("-"))
        table.setItem(row, self.COL_CLOSE, QTableWidgetItem("-"))
        table.setItem(row, self.COL_VOLUME, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPT_HIST_VOL, QTableWidgetItem("-"))
        table.setItem(row, self.COL_OPT_IMPL_VOL, QTableWidgetItem("-"))

        delete_item = QTableWidgetItem("X")
        delete_item.setForeground(QColor("red"))
        font = delete_item.font()
        font.setBold(True)
        delete_item.setFont(font)
        delete_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, self.COL_DELETE, delete_item)

    def _on_delete_symbol(self, symbol: str) -> None:
        """Handle delete button click for a symbol."""
        if self._vm:
            self._vm.remove_symbol(symbol)

    def _on_order_changed(self, symbols: list) -> None:
        """Handle row order change from drag-drop."""
        if not self._vm:
            return

        # Persist new order via viewmodel
        self._vm.update_watchlist_order(symbols)

        # Recreate view buttons for all rows (they don't transfer during drag)
        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            self._recreate_view_buttons(table)

        self.status_label.setText("Watchlist order updated")
        log.debug(f"ETF watchlist order changed: {symbols}")

    def _recreate_view_buttons(self, table: QTableWidget) -> None:
        """Recreate view buttons for all rows after drag-drop reorder."""
        for row in range(table.rowCount()):
            symbol_item = table.item(row, self.COL_SYMBOL)
            if not symbol_item:
                continue

            symbol = symbol_item.text()

            # Only recreate if button is missing
            if table.cellWidget(row, self.COL_VIEW) is None:
                view_btn = QPushButton("📈")
                view_btn.setObjectName(f"etf_watchlist_view_{symbol.lower()}_button")
                view_btn.setToolTip(f"View chart for {symbol}")
                view_btn.setMaximumWidth(40)
                view_btn.clicked.connect(lambda checked, s=symbol: self._on_view_clicked(s))
                table.setCellWidget(row, self.COL_VIEW, view_btn)

    def _on_watchlist_cell_clicked(self, row: int, column: int) -> None:
        """Handle single-click on watchlist cell - check for delete column."""
        if column != self.COL_DELETE or not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        symbol_item = table.item(row, self.COL_SYMBOL)
        if symbol_item:
            self._on_delete_symbol(symbol_item.text())

    def _on_active_watchlist_loaded(self, symbols: list) -> None:
        """Handle symbols loaded for active watchlist."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        table.setRowCount(len(symbols))
        for i, symbol in enumerate(symbols):
            self._init_row(table, i, symbol)

        self.status_label.setText(f"Loaded {len(symbols)} symbols")

    def _on_create_watchlist(self) -> None:
        """Handle create watchlist button click."""
        from src.presentation.components.create_watchlist_dialog import CreateWatchlistDialog

        existing_names = self._vm.get_existing_watchlist_names() if self._vm else []
        name, accepted = CreateWatchlistDialog.get_watchlist_name(self, existing_names)

        if accepted and name and self._vm:
            self._vm.create_watchlist(name)

    def _on_delete_watchlist(self, watchlist_id: str) -> None:
        """Handle delete watchlist request."""
        reply = QMessageBox.question(
            self,
            "Delete Watchlist",
            "Are you sure you want to delete this watchlist?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self._vm:
            self._vm.delete_watchlist(watchlist_id)

    def _on_rename_watchlist(self, watchlist_id: str, new_name: str) -> None:
        """Handle rename watchlist request."""
        if self._vm:
            self._vm.rename_watchlist(watchlist_id, new_name)
            self.status_label.setText(f"Renamed watchlist to '{new_name}'")

    def _on_add_clicked(self) -> None:
        symbol = self.ticker_input.text().strip().upper()
        if not symbol or not self._vm:
            return

        self.ticker_input.clear()

        if symbol in self._vm.symbols:
            self.status_label.setText(f"{symbol} is already in the watchlist")
            return

        if self._vm.asset_exists(symbol):
            self._vm.add_symbol(symbol)
        else:
            self._vm.fetch_and_create_asset(symbol)

    def _on_add_from_assets(self) -> None:
        """Open dialog to add assets from saved assets."""
        from src.presentation.components.asset_selection_dialog import AssetSelectionDialog

        if not self._vm:
            return

        assets = self._vm.get_all_saved_assets()
        current_symbols = list(self._vm.symbols)

        selected, accepted = AssetSelectionDialog.select_assets(
            assets, current_symbols, self
        )

        if accepted and selected:
            count = self._vm.add_symbols(selected)
            self.status_label.setText(f"Added {count} symbols from assets")

    def _on_contracts_received(self, symbol: str, details_list: list) -> None:
        """Handle multiple contracts found - show selection dialog."""
        from src.presentation.components.contract_selection_dialog import ContractSelectionDialog

        self._stop_loading()

        selected_cd, accepted = ContractSelectionDialog.select_contract(
            symbol, details_list, self
        )

        if accepted and selected_cd:
            self._start_loading()
            self._vm.create_asset_from_selection(symbol, selected_cd)
        else:
            self.status_label.setText(f"Selection cancelled for {symbol}")

    def _on_asset_created(self, symbol: str) -> None:
        """Handle asset created signal."""
        self._stop_loading()
        self.status_label.setText(f"Asset {symbol} created from IB")

    def _on_asset_creation_error(self, symbol: str, error: str) -> None:
        """Handle asset creation error."""
        self._stop_loading()
        self.status_label.setText(f"Error adding {symbol}: {error}")

    def _on_asset_creation_started(self, symbol: str) -> None:
        """Handle asset creation started - show loading status."""
        self.status_label.setText(f"Searching IB for {symbol}...")
        self._start_loading()

    def _start_loading(self) -> None:
        """Start the loading spinner animation."""
        self._is_loading = True
        self._spinner_frame = 0
        self.loading_label.setVisible(True)
        self.loading_label.setText(self.SPINNER_FRAMES[0] + " Searching...")
        self.add_button.setEnabled(False)
        self.ticker_input.setEnabled(False)
        self._spinner_timer.start(80)  # 80ms per frame for smooth animation

    def _stop_loading(self) -> None:
        """Stop the loading spinner animation."""
        self._is_loading = False
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.loading_label.setText("")
        self.add_button.setEnabled(True)
        self.ticker_input.setEnabled(True)

    def _update_spinner(self) -> None:
        """Update the spinner animation frame."""
        if not self._is_loading:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        self.loading_label.setText(self.SPINNER_FRAMES[self._spinner_frame] + " Searching...")

    def _on_symbol_added(self, symbol: str) -> None:
        if not self._vm:
            return

        self._stop_loading()
        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            row = table.rowCount()
            table.insertRow(row)
            self._init_row(table, row, symbol)
        self.status_label.setText(f"Added {symbol}")

    def _on_symbols_added(self, symbols: list) -> None:
        self.status_label.setText(f"Added {len(symbols)} symbols")

    def _on_symbol_removed(self, symbol: str) -> None:
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if table:
            for row in range(table.rowCount()):
                item = table.item(row, self.COL_SYMBOL)
                if item and item.text() == symbol:
                    table.removeRow(row)
                    break
        self.status_label.setText(f"Removed {symbol}")

    def _on_error(self, message: str) -> None:
        self.status_label.setText(f"Error: {message}")

    def _format_number(self, value: float, decimals: int = 2) -> str:
        """Format a number for display, handling zero/None values."""
        if value is None or value == 0:
            return "-"
        return f"{value:,.{decimals}f}"

    def _format_volume(self, value: int) -> str:
        """Format volume with K/M suffix."""
        if value is None or value == 0:
            return "-"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return str(value)

    def _format_percent(self, value: float) -> str:
        """Format percentage value."""
        if value is None or value == 0:
            return "-"
        return f"{value:+.2f}%"

    def _on_tick_updated(self, symbol: str, tick_data: dict) -> None:
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        for row in range(table.rowCount()):
            item = table.item(row, self.COL_SYMBOL)
            if item and item.text() == symbol:
                if "bid_size" in tick_data and tick_data["bid_size"]:
                    table.setItem(row, self.COL_BID_SIZE, QTableWidgetItem(str(tick_data["bid_size"])))
                if "bid" in tick_data and tick_data["bid"]:
                    table.setItem(row, self.COL_BID, QTableWidgetItem(self._format_number(tick_data["bid"])))
                if "last" in tick_data and tick_data["last"]:
                    last_item = QTableWidgetItem(self._format_number(tick_data["last"]))
                    font = last_item.font()
                    font.setBold(True)
                    last_item.setFont(font)
                    last_item.setBackground(QColor("#e3f2fd"))
                    last_item.setForeground(QColor("black"))
                    table.setItem(row, self.COL_LAST, last_item)
                if "ask" in tick_data and tick_data["ask"]:
                    table.setItem(row, self.COL_ASK, QTableWidgetItem(self._format_number(tick_data["ask"])))
                if "ask_size" in tick_data and tick_data["ask_size"]:
                    table.setItem(row, self.COL_ASK_SIZE, QTableWidgetItem(str(tick_data["ask_size"])))

                if "open" in tick_data and tick_data["open"]:
                    table.setItem(row, self.COL_OPEN, QTableWidgetItem(self._format_number(tick_data["open"])))
                if "high" in tick_data and tick_data["high"]:
                    table.setItem(row, self.COL_HIGH, QTableWidgetItem(self._format_number(tick_data["high"])))
                if "low" in tick_data and tick_data["low"]:
                    table.setItem(row, self.COL_LOW, QTableWidgetItem(self._format_number(tick_data["low"])))
                if "close" in tick_data and tick_data["close"]:
                    table.setItem(row, self.COL_CLOSE, QTableWidgetItem(self._format_number(tick_data["close"])))

                last_price = tick_data.get("last", 0)
                close_price = tick_data.get("close", 0)
                if last_price and close_price:
                    change_pct = ((last_price - close_price) / close_price) * 100
                    change_item = QTableWidgetItem(self._format_percent(change_pct))
                    bg_color = self.get_change_color(change_pct)
                    change_item.setBackground(QColor(bg_color))
                    text_color = "white" if self.is_dark_color(bg_color) else "black"
                    change_item.setForeground(QColor(text_color))
                    table.setItem(row, self.COL_CHANGE, change_item)

                if "volume" in tick_data and tick_data["volume"]:
                    table.setItem(row, self.COL_VOLUME, QTableWidgetItem(self._format_volume(tick_data["volume"])))

                if "option_historical_vol" in tick_data and tick_data["option_historical_vol"]:
                    hv = tick_data["option_historical_vol"]
                    hv_pct = hv * 100 if hv < 1 else hv
                    table.setItem(row, self.COL_OPT_HIST_VOL, QTableWidgetItem(f"{hv_pct:.1f}%"))
                if "option_implied_vol" in tick_data and tick_data["option_implied_vol"]:
                    iv = tick_data["option_implied_vol"]
                    iv_pct = iv * 100 if iv < 1 else iv
                    table.setItem(row, self.COL_OPT_IMPL_VOL, QTableWidgetItem(f"{iv_pct:.1f}%"))

                break

    def _on_watchlist_item_double_clicked(self, row: int, column: int) -> None:
        """Handle double-click on watchlist row - open detail window."""
        if not self._vm:
            return

        active_id = self._vm.active_watchlist_id
        table = self._tables.get(active_id)
        if not table:
            return

        symbol_item = table.item(row, self.COL_SYMBOL)
        if not symbol_item:
            return

        symbol = symbol_item.text()
        self._open_detail_window(symbol)

    def _on_view_clicked(self, symbol: str) -> None:
        """Handle view button click - open detail window."""
        self._open_detail_window(symbol)

    def _open_detail_window(self, symbol: str) -> None:
        """Open the asset detail window for the given symbol."""
        try:
            app = get_app()
            asset = app.asset_service.get_asset("ETF", symbol)
            if asset:
                from src.presentation.windows.asset_detail import AssetDetailWindow
                self._detail_window = AssetDetailWindow(asset, parent=self.window())
                self._detail_window.show()
                self.status_label.setText(f"Opened detail for {symbol}")
            else:
                self.status_label.setText(f"Asset {symbol} not found in saved assets")
        except Exception as e:
            self.status_label.setText(f"Error opening detail: {e}")
            log.error(f"Error opening asset detail: {e}")
            import traceback
            traceback.print_exc()

    def onDestroy(self) -> None:
        if self._vm:
            self._vm.dispose()
        if self._detail_window:
            self._detail_window.close()
            self._detail_window = None
        super().onDestroy()


class AssetsPage(BaseView):
    """Asset Management Page."""

    # Loading spinner frames for animation
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Signals for thread-safe UI updates
    asset_added = pyqtSignal(str)  # Emitted with symbol when asset is added
    asset_error = pyqtSignal(str)  # Emitted with error message
    contracts_received = pyqtSignal(str, list)  # Emitted with symbol and details list for selection

    def __init__(self, asset_type: str = "STOCK", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.asset_type = asset_type
        self.setObjectName(f"{asset_type.lower()}_assets_page")
        self._spinner_frame = 0  # Current spinner animation frame
        self._spinner_timer = None  # Timer for spinner animation
        self._is_loading = False  # Loading state flag

        # Connect signals to slots
        self.asset_added.connect(self._on_asset_added)
        self.asset_error.connect(self._on_asset_error)
        self.contracts_received.connect(self._on_contracts_received)

        self._setup_ui()
        self._load_assets()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QHBoxLayout()
        title = QLabel(f"{self.asset_type.title()} Assets")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.symbol_input = QLineEdit()
        self.symbol_input.setObjectName(f"{self.asset_type.lower()}_symbol_input")
        self.symbol_input.setPlaceholderText("Enter symbol...")
        self.symbol_input.setMaximumWidth(120)
        self.symbol_input.returnPressed.connect(self._on_add_clicked)
        header.addWidget(self.symbol_input)

        self.add_button = QPushButton("Add Asset")
        self.add_button.setObjectName(f"{self.asset_type.lower()}_add_asset_button")
        self.add_button.clicked.connect(self._on_add_clicked)
        header.addWidget(self.add_button)

        # Loading spinner label (hidden by default)
        self.loading_label = QLabel("")
        self.loading_label.setObjectName(f"{self.asset_type.lower()}_loading_label")
        self.loading_label.setStyleSheet("color: #2196F3; font-size: 14px; margin-left: 5px;")
        self.loading_label.setVisible(False)
        header.addWidget(self.loading_label)

        # Spinner timer for animation
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._update_spinner)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setObjectName(f"{self.asset_type.lower()}_refresh_button")
        self.refresh_button.clicked.connect(self._load_assets)
        header.addWidget(self.refresh_button)

        layout.addLayout(header)

        self.status_label = QLabel("")
        self.status_label.setObjectName(f"{self.asset_type.lower()}_assets_status")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setObjectName(f"{self.asset_type.lower()}_assets_table")
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["", "Symbol", "Name", "Exchange", "Currency", ""]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 50)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(5, 50)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_asset_double_clicked)
        layout.addWidget(self.table)

        # Reference to hold detail window (prevent garbage collection)
        self._detail_window: Optional[object] = None

    def _load_assets(self) -> None:
        try:
            app = get_app()
            assets = app.asset_service.get_all_assets(self.asset_type)
            self.table.setRowCount(len(assets))
            for i, asset in enumerate(assets):
                # Get name/exchange/currency from contract details if available
                name = ""
                exchange = ""
                currency = ""
                if asset.contract_details:
                    cd = asset.contract_details[0]
                    if hasattr(cd, 'long_name'):
                        name = cd.long_name or ""
                    if hasattr(cd, 'contract') and cd.contract:
                        exchange = getattr(cd.contract, 'primary_exchange', "") or getattr(cd.contract, 'exchange', "") or ""
                        currency = getattr(cd.contract, 'currency', "") or ""

                # Add view button with chart icon (first column)
                view_btn = QPushButton("📈")
                view_btn.setObjectName(f"view_{asset.symbol.lower()}_button")
                view_btn.setToolTip(f"View chart for {asset.symbol}")
                view_btn.setMaximumWidth(40)
                view_btn.clicked.connect(lambda checked, s=asset.symbol: self._on_view_clicked(s))
                self.table.setCellWidget(i, 0, view_btn)

                self.table.setItem(i, 1, QTableWidgetItem(asset.symbol))
                self.table.setItem(i, 2, QTableWidgetItem(name))
                self.table.setItem(i, 3, QTableWidgetItem(exchange))
                self.table.setItem(i, 4, QTableWidgetItem(currency))

                # Add delete button with trash icon (last column)
                delete_btn = QPushButton("🗑️")
                delete_btn.setObjectName(f"delete_{asset.symbol.lower()}_button")
                delete_btn.setToolTip(f"Delete {asset.symbol}")
                delete_btn.setMaximumWidth(40)
                delete_btn.clicked.connect(
                    lambda checked, s=asset.symbol, r=i: self._on_delete_row_clicked(s, r)
                )
                self.table.setCellWidget(i, 5, delete_btn)
            self.status_label.setText(f"Loaded {len(assets)} assets")
        except Exception as e:
            self.status_label.setText(f"Error loading assets: {e}")
            log.error(f"Failed to load assets: {e}")
            import traceback
            traceback.print_exc()

    def _on_add_clicked(self) -> None:
        symbol = self.symbol_input.text().strip().upper()
        if not symbol:
            return

        try:
            app = get_app()

            # Check if broker is connected
            from src.core.interfaces.broker import IBrokerClient
            if not app.container.is_registered(IBrokerClient):
                self.status_label.setText(f"Error: Broker not configured")
                return

            broker = app.container.resolve(IBrokerClient)
            if not broker.is_connected():
                self.status_label.setText(f"Error: Not connected to IB - click Connect first")
                return

            # Check if asset already exists
            if app.asset_service.exists(self.asset_type, symbol):
                self.status_label.setText(f"Asset {symbol} already exists")
                return

            self.status_label.setText(f"Searching IB for {symbol}...")
            self.symbol_input.clear()
            self._start_loading()

            # Create contract based on asset type
            # Don't specify exchange for initial search to get all matching contracts
            from src.domain.entities.contract import StockContract, FutureContract, ETFContract
            from src.domain.entities.asset import Asset, AssetType

            if self.asset_type in ("STOCK", "ETF"):
                # Use empty exchange and primary_exchange to search for all matching contracts
                # ETFs use STK security type like stocks
                if self.asset_type == "STOCK":
                    contract = StockContract.create(symbol=symbol, exchange="", primary_exchange="")
                else:
                    contract = ETFContract.create(symbol=symbol, exchange="", primary_exchange="")

                # Fetch contract details from IB
                # Store reference to self for use in callback
                page_ref = self

                def on_details_received(details_list):
                    if not details_list:
                        page_ref.asset_error.emit(f"No contract found for {symbol}")
                        return

                    # If multiple contracts match, let user choose
                    if len(details_list) > 1:
                        # Emit signal to show selection dialog on main thread
                        page_ref.contracts_received.emit(symbol, details_list)
                        return

                    # Single match - save directly
                    asset = Asset(
                        symbol=symbol,
                        asset_type=AssetType.from_str(page_ref.asset_type),
                        contract_details=details_list,
                    )
                    app.asset_service.save_asset(asset)

                    # Emit signal to refresh UI on main thread
                    page_ref.asset_added.emit(symbol)

                app.asset_service.fetch_contract_details(
                    self.asset_type, contract, callback=on_details_received
                )
            else:
                # For futures, try multiple exchanges to find the contract
                # Common futures exchanges: GLOBEX (CME), NYMEX, ECBOT, NYBOT
                exchanges_to_try = ["GLOBEX", "NYMEX", "ECBOT", "NYBOT", ""]
                page_ref = self
                all_details = []
                exchanges_tried = [0]  # Use list to allow mutation in closure

                def try_next_exchange():
                    if exchanges_tried[0] >= len(exchanges_to_try):
                        # All exchanges tried, process results
                        if not all_details:
                            page_ref.asset_error.emit(f"No contract found for {symbol}")
                            return

                        if len(all_details) > 1:
                            page_ref.contracts_received.emit(symbol, all_details)
                        else:
                            asset = Asset(
                                symbol=symbol,
                                asset_type=AssetType.from_str(page_ref.asset_type),
                                contract_details=all_details,
                            )
                            app.asset_service.save_asset(asset)
                            page_ref.asset_added.emit(symbol)
                        return

                    exchange = exchanges_to_try[exchanges_tried[0]]
                    exchanges_tried[0] += 1
                    # Important: leave local_symbol empty for search (not symbol)
                    contract = FutureContract.create(symbol=symbol, exchange=exchange, local_symbol="")

                    def on_details_received(details_list):
                        if details_list:
                            all_details.extend(details_list)
                        try_next_exchange()

                    app.asset_service.fetch_contract_details(
                        page_ref.asset_type, contract, callback=on_details_received
                    )

                try_next_exchange()

        except Exception as e:
            self.status_label.setText(f"Error: {e}")
            log.error(f"Error adding asset: {e}")
            import traceback
            traceback.print_exc()

    def _on_delete_row_clicked(self, symbol: str, row: int) -> None:
        """Handle delete button click for a specific row."""
        self._show_delete_dialog(symbol)

    def _show_delete_dialog(self, symbol: str) -> None:
        """Show dialog with options for deleting an asset."""
        asset_type_label = self.asset_type.title()

        msg_box = QMessageBox(self)
        msg_box.setObjectName(f"delete_dialog_{symbol.lower()}")
        msg_box.setWindowTitle(f"Delete {asset_type_label} Asset")
        msg_box.setText(f"How would you like to delete {symbol}?")
        msg_box.setInformativeText(
            "• Delete asset only: Removes asset file but keeps historical data\n"
            "• Delete with all data: Removes asset file AND ALL historical "
            "data (cannot be undone)"
        )

        delete_asset_btn = msg_box.addButton(
            "Delete asset only", QMessageBox.ButtonRole.AcceptRole
        )
        delete_asset_btn.setObjectName(f"delete_asset_only_{symbol.lower()}_button")

        delete_all_btn = msg_box.addButton(
            "Delete with all data", QMessageBox.ButtonRole.DestructiveRole
        )
        delete_all_btn.setObjectName(f"delete_with_data_{symbol.lower()}_button")
        delete_all_btn.setStyleSheet("background-color: #d32f2f; color: white;")

        cancel_btn = msg_box.addButton(QMessageBox.StandardButton.Cancel)
        cancel_btn.setObjectName(f"cancel_delete_{symbol.lower()}_button")

        msg_box.setDefaultButton(cancel_btn)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == delete_asset_btn:
            self._delete_asset_only(symbol)
        elif clicked == delete_all_btn:
            # Show final confirmation for destructive action
            confirm = QMessageBox.warning(
                self,
                "Confirm Deletion",
                f"This will permanently delete ALL historical data for {symbol}."
                "\n\nThis action cannot be undone!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self._delete_asset_with_data(symbol)

    def _delete_asset_only(self, symbol: str) -> None:
        """Delete only the asset file, keeping historical data."""
        try:
            app = get_app()
            app.asset_service.delete_asset(self.asset_type, symbol)
            self._load_assets()  # Refresh table
            self.status_label.setText(f"Deleted {symbol}")
        except Exception as e:
            self.status_label.setText(f"Error deleting: {e}")

    def _delete_asset_with_data(self, symbol: str) -> None:
        """Delete asset file and all historical data for futures."""
        try:
            app = get_app()

            # Delete historical data for all contracts matching this symbol
            deleted_count = 0
            try:
                historical_service = app.historical_data_service
                # Delete matching data for common timeframes
                for timeframe in ["1 day", "1 hour", "5 mins"]:
                    count = historical_service.delete_historical_data_matching(
                        symbol, timeframe
                    )
                    deleted_count += count
                log.info(
                    f"Deleted {deleted_count} historical data items for {symbol}"
                )
            except Exception as e:
                log.warning(f"Error deleting historical data for {symbol}: {e}")

            # Delete the asset file
            app.asset_service.delete_asset(self.asset_type, symbol)
            self._load_assets()  # Refresh table
            self.status_label.setText(
                f"Deleted {symbol} and {deleted_count} historical data items"
            )
        except Exception as e:
            self.status_label.setText(f"Error deleting: {e}")
            log.error(f"Error deleting {symbol} with data: {e}")

    def _on_asset_double_clicked(self, row: int, column: int) -> None:
        """Handle double-click on asset row - open detail window."""
        symbol_item = self.table.item(row, 1)
        if not symbol_item:
            return

        symbol = symbol_item.text()
        try:
            app = get_app()
            asset = app.asset_service.get_asset(self.asset_type, symbol)
            if asset:
                from src.presentation.windows.asset_detail import AssetDetailWindow
                self._detail_window = AssetDetailWindow(asset, parent=self.window())
                self._detail_window.show()
                self.status_label.setText(f"Opened detail for {symbol}")
            else:
                self.status_label.setText(f"Asset {symbol} not found")
        except Exception as e:
            self.status_label.setText(f"Error opening detail: {e}")
            log.error(f"Error opening asset detail: {e}")
            import traceback
            traceback.print_exc()

    def _on_view_clicked(self, symbol: str) -> None:
        """Handle view button click - open detail window."""
        try:
            app = get_app()
            asset = app.asset_service.get_asset(self.asset_type, symbol)
            if asset:
                from src.presentation.windows.asset_detail import AssetDetailWindow
                self._detail_window = AssetDetailWindow(asset, parent=self.window())
                self._detail_window.show()
                self.status_label.setText(f"Opened detail for {symbol}")
            else:
                self.status_label.setText(f"Asset {symbol} not found")
        except Exception as e:
            self.status_label.setText(f"Error opening detail: {e}")
            log.error(f"Error opening asset detail: {e}")
            import traceback
            traceback.print_exc()

    def _start_loading(self) -> None:
        """Start the loading spinner animation."""
        self._is_loading = True
        self._spinner_frame = 0
        self.loading_label.setVisible(True)
        self.loading_label.setText(self.SPINNER_FRAMES[0] + " Searching...")
        self.add_button.setEnabled(False)
        self.symbol_input.setEnabled(False)
        self._spinner_timer.start(80)  # 80ms per frame for smooth animation

    def _stop_loading(self) -> None:
        """Stop the loading spinner animation."""
        self._is_loading = False
        self._spinner_timer.stop()
        self.loading_label.setVisible(False)
        self.loading_label.setText("")
        self.add_button.setEnabled(True)
        self.symbol_input.setEnabled(True)

    def _update_spinner(self) -> None:
        """Update the spinner animation frame."""
        if not self._is_loading:
            return
        self._spinner_frame = (self._spinner_frame + 1) % len(self.SPINNER_FRAMES)
        self.loading_label.setText(self.SPINNER_FRAMES[self._spinner_frame] + " Searching...")

    @pyqtSlot(str)
    def _on_asset_added(self, symbol: str) -> None:
        """Handle asset added signal - refresh table on main thread."""
        self._stop_loading()
        self._load_assets()
        self.status_label.setText(f"Added {symbol} successfully")

    @pyqtSlot(str)
    def _on_asset_error(self, error: str) -> None:
        """Handle asset error signal - show error on main thread."""
        self._stop_loading()
        self.status_label.setText(error)

    @pyqtSlot(str, list)
    def _on_contracts_received(self, symbol: str, details_list: list) -> None:
        """Handle multiple contracts found - show selection dialog on main thread."""
        self._stop_loading()
        self.status_label.setText(f"Multiple contracts found for {symbol} - please select one")

        # Create selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Select Contract for {symbol}")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout(dialog)

        # Instructions
        label = QLabel(f"Found {len(details_list)} contracts matching '{symbol}'. Please select one:")
        layout.addWidget(label)

        # List widget with contracts
        list_widget = QListWidget()
        list_widget.setObjectName("contract_selection_list")

        for i, cd in enumerate(details_list):
            # Build descriptive text for each contract
            contract = cd.contract
            name = cd.long_name or ""
            exchange = getattr(contract, 'primary_exchange', "") or getattr(contract, 'exchange', "") or ""
            currency = getattr(contract, 'currency', "") or ""
            sec_type = getattr(contract, 'sec_type', "") or ""
            local_symbol = getattr(contract, 'local_symbol', "") or ""

            # Format: "NAME (EXCHANGE, CURRENCY) - Type: SEC_TYPE"
            display_text = f"{name}" if name else symbol
            if exchange or currency:
                display_text += f" ({exchange}"
                if currency:
                    display_text += f", {currency}"
                display_text += ")"
            if local_symbol and local_symbol != symbol:
                display_text += f" [{local_symbol}]"
            if sec_type:
                display_text += f" - Type: {sec_type}"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, i)  # Store index
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.setObjectName("contract_selection_buttons")
        ok_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setObjectName("contract_selection_ok_button")
        cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("contract_selection_cancel_button")
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Double-click to select
        list_widget.itemDoubleClicked.connect(dialog.accept)

        # Select first item by default
        if list_widget.count() > 0:
            list_widget.setCurrentRow(0)

        # Show dialog and handle result
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_item = list_widget.currentItem()
            if selected_item:
                selected_index = selected_item.data(Qt.ItemDataRole.UserRole)
                selected_cd = details_list[selected_index]

                # Save only the selected contract
                from src.domain.entities.asset import Asset, AssetType
                asset = Asset(
                    symbol=symbol,
                    asset_type=AssetType.from_str(self.asset_type),
                    contract_details=[selected_cd],  # Only the selected one
                )

                try:
                    app = get_app()
                    app.asset_service.save_asset(asset)
                    self._load_assets()
                    self.status_label.setText(f"Added {symbol} ({selected_cd.long_name or 'selected'}) successfully")
                except Exception as e:
                    self.status_label.setText(f"Error saving asset: {e}")
                    log.error(f"Error saving selected contract: {e}")
        else:
            self.status_label.setText(f"Selection cancelled for {symbol}")


class MainWindow(BaseWindow):
    """Main application window."""

    # US Market hours (Eastern Time)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    PRE_MARKET_START = time(4, 0)
    AFTER_HOURS_END = time(20, 0)
    EASTERN_TZ = ZoneInfo("America/New_York")

    def __init__(self, workspace_id: Optional[int] = None, *args: Tuple[str, Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        log.info("MainWindow initializing...")
        self.workspace_id = workspace_id
        self.setObjectName("main_window")

        # Set dynamic window title based on workspace ID
        if self.workspace_id is not None:
            self.setWindowTitle(f"FinanceApp [{self.workspace_id}]")
        else:
            self.setWindowTitle("FinanceApp")

        self.resize(1200, 800)

        self._is_connected = False

        self._setup_ui()
        self._setup_status_bar()
        self._setup_menu()

        # Timer to update market status every second
        self._market_timer = QTimer(self)
        self._market_timer.timeout.connect(self._update_market_status)
        self._market_timer.start(1000)
        self._update_market_status()  # Initial update

        # Start with home page
        self.setCurrentPage(HomePage)()

        # Auto-connect to IB
        QTimer.singleShot(100, self._auto_connect)

        log.info("MainWindow initialized")

    def _setup_ui(self) -> None:
        self.page_container = QStackedWidget()
        self.page_container.setObjectName("page_container")
        self.setCentralWidget(self.page_container)

    def _setup_status_bar(self) -> None:
        """Setup the bottom status bar with connection and market info."""
        status_bar = QStatusBar()
        status_bar.setObjectName("main_status_bar")
        self.setStatusBar(status_bar)

        # Left side - Connection status and controls
        left_widget = QWidget()
        left_layout = QHBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 0, 5, 0)
        left_layout.setSpacing(10)

        # Connection status label
        self._connection_label = QLabel("Disconnected")
        self._connection_label.setObjectName("connection_status_label")
        self._connection_label.setStyleSheet("color: red; font-weight: bold;")
        left_layout.addWidget(self._connection_label)

        # Connect button
        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("connect_button")
        self._connect_btn.setMaximumWidth(80)
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        left_layout.addWidget(self._connect_btn)

        # Disconnect button
        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setObjectName("disconnect_button")
        self._disconnect_btn.setMinimumWidth(90)
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        left_layout.addWidget(self._disconnect_btn)

        # Status message
        self._status_message = QLabel("")
        self._status_message.setObjectName("status_message")
        left_layout.addWidget(self._status_message)

        left_layout.addStretch()
        status_bar.addWidget(left_widget, 1)

        # Right side - Market status
        right_widget = QWidget()
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 10, 0)
        right_layout.setSpacing(20)

        # Market countdown
        self._market_countdown = QLabel("")
        self._market_countdown.setObjectName("market_countdown")
        right_layout.addWidget(self._market_countdown)

        # Market status
        self._market_status = QLabel("Market: --")
        self._market_status.setObjectName("market_status_label")
        self._market_status.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(self._market_status)

        status_bar.addPermanentWidget(right_widget)

    def _auto_connect(self) -> None:
        """Auto-connect to IB on startup."""
        # Check if already connected (e.g., started from main.py)
        try:
            app = get_app()
            if app._started:
                from src.core.interfaces.broker import IBrokerClient
                if app.container.is_registered(IBrokerClient):
                    broker = app.container.resolve(IBrokerClient)
                    if broker.is_connected():
                        self._update_connection_status(True)
                        return
        except Exception:
            pass

        # Try to connect
        self._on_connect_clicked()

    def _on_connect_clicked(self) -> None:
        """Handle connect button click."""
        self._status_message.setText("Connecting to IB...")
        self._connect_btn.setEnabled(False)

        # Connect in background thread to not block UI
        def connect_task():
            try:
                app = get_app()
                if not app._started:
                    app.start()

                # Use wait_for_connection with proper event-based confirmation
                from src.core.interfaces.broker import IBrokerClient
                from src.infrastructure.broker import ConnectionState

                if app.container.is_registered(IBrokerClient):
                    broker = app.container.resolve(IBrokerClient)

                    # Wait for connection (blocking with timeout)
                    connected = broker.wait_for_connection(timeout=15.0)

                    # Update UI from main thread
                    if connected and broker.is_connected():
                        QTimer.singleShot(0, lambda: self._update_connection_status(True))
                    else:
                        error_msg = broker.connection_error or "Connection timeout - is TWS/Gateway running?"
                        QTimer.singleShot(0, lambda: self._update_connection_status(False, error_msg))
                else:
                    QTimer.singleShot(0, lambda: self._update_connection_status(
                        False, "Broker not registered"
                    ))

            except Exception as e:
                log.error(f"Connection error: {e}")
                QTimer.singleShot(0, lambda: self._update_connection_status(False, str(e)))

        thread = threading.Thread(target=connect_task, daemon=True)
        thread.start()

    def _on_disconnect_clicked(self) -> None:
        """Handle disconnect button click."""
        self._status_message.setText("Disconnecting...")
        self._disconnect_btn.setEnabled(False)

        try:
            app = get_app()
            from src.core.interfaces.broker import IBrokerClient
            if app.container.is_registered(IBrokerClient):
                broker = app.container.resolve(IBrokerClient)
                if broker.is_connected():
                    broker.disconnect()
            self._update_connection_status(False)
        except Exception as e:
            log.error(f"Disconnect error: {e}")
            self._update_connection_status(False, str(e))

    @pyqtSlot()
    def _update_connection_status(self, connected: bool, error: str = "") -> None:
        """Update the connection status in the UI."""
        self._is_connected = connected

        if connected:
            self._connection_label.setText("Connected")
            self._connection_label.setStyleSheet("color: #00aa00; font-weight: bold;")
            self._status_message.setText("Connected to IB")
            self._connect_btn.setEnabled(False)
            self._disconnect_btn.setEnabled(True)
        else:
            self._connection_label.setText("Disconnected")
            self._connection_label.setStyleSheet("color: red; font-weight: bold;")
            if error:
                self._status_message.setText(f"Error: {error}")
            else:
                self._status_message.setText("")
            self._connect_btn.setEnabled(True)
            self._disconnect_btn.setEnabled(False)

    def _update_market_status(self) -> None:
        """Update market status and countdown."""
        now = datetime.now(self.EASTERN_TZ)
        current_time = now.time()
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Weekend check
        if weekday >= 5:  # Saturday or Sunday
            self._market_status.setText("Market: Closed")
            self._market_status.setStyleSheet("color: red; font-weight: bold;")
            # Calculate time until Monday pre-market
            days_until_monday = (7 - weekday) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            next_open = datetime.combine(
                now.date() + timedelta(days=days_until_monday),
                self.PRE_MARKET_START,
                tzinfo=self.EASTERN_TZ
            )
            delta = next_open - now
            self._market_countdown.setText(f"Opens in {self._format_timedelta(delta)}")
            return

        # Pre-market (4:00 AM - 9:30 AM ET)
        if self.PRE_MARKET_START <= current_time < self.MARKET_OPEN:
            self._market_status.setText("Market: Pre-Market")
            self._market_status.setStyleSheet("color: orange; font-weight: bold;")
            market_open = datetime.combine(now.date(), self.MARKET_OPEN, tzinfo=self.EASTERN_TZ)
            delta = market_open - now
            self._market_countdown.setText(f"Opens in {self._format_timedelta(delta)}")

        # Market open (9:30 AM - 4:00 PM ET)
        elif self.MARKET_OPEN <= current_time < self.MARKET_CLOSE:
            self._market_status.setText("Market: Open")
            self._market_status.setStyleSheet("color: #00aa00; font-weight: bold;")
            market_close = datetime.combine(now.date(), self.MARKET_CLOSE, tzinfo=self.EASTERN_TZ)
            delta = market_close - now
            self._market_countdown.setText(f"Closes in {self._format_timedelta(delta)}")

        # After hours (4:00 PM - 8:00 PM ET)
        elif self.MARKET_CLOSE <= current_time < self.AFTER_HOURS_END:
            self._market_status.setText("Market: After-Hours")
            self._market_status.setStyleSheet("color: orange; font-weight: bold;")
            after_close = datetime.combine(now.date(), self.AFTER_HOURS_END, tzinfo=self.EASTERN_TZ)
            delta = after_close - now
            self._market_countdown.setText(f"Ends in {self._format_timedelta(delta)}")

        # Closed (before 4:00 AM or after 8:00 PM)
        else:
            self._market_status.setText("Market: Closed")
            self._market_status.setStyleSheet("color: red; font-weight: bold;")
            # Calculate next pre-market open
            if current_time < self.PRE_MARKET_START:
                next_open = datetime.combine(now.date(), self.PRE_MARKET_START, tzinfo=self.EASTERN_TZ)
            else:
                # After 8 PM, next day
                next_day = now.date() + timedelta(days=1)
                # Skip to Monday if Friday night
                if weekday == 4:  # Friday
                    next_day = now.date() + timedelta(days=3)
                next_open = datetime.combine(next_day, self.PRE_MARKET_START, tzinfo=self.EASTERN_TZ)
            delta = next_open - now
            self._market_countdown.setText(f"Opens in {self._format_timedelta(delta)}")

    def _format_timedelta(self, delta: timedelta) -> str:
        """Format timedelta as HH:MM:SS or Xd HH:MM:SS."""
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return "00:00:00"

        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        home_action = file_menu.addAction("Home")
        home_action.setObjectName("action_home")
        home_action.triggered.connect(self.setCurrentPage(HomePage))

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setObjectName("action_exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self._quit_application)

        # Assets menu
        assets_menu = menubar.addMenu("Assets")

        stocks_assets_action = assets_menu.addAction("Stocks")
        stocks_assets_action.setObjectName("action_stocks_assets")
        stocks_assets_action.triggered.connect(self.setCurrentPage(AssetsPage, asset_type="STOCK"))

        futures_assets_action = assets_menu.addAction("Futures")
        futures_assets_action.setObjectName("action_futures_assets")
        futures_assets_action.triggered.connect(self.setCurrentPage(AssetsPage, asset_type="FUTURE"))

        etf_assets_action = assets_menu.addAction("ETF")
        etf_assets_action.setObjectName("action_etf_assets")
        etf_assets_action.triggered.connect(self.setCurrentPage(AssetsPage, asset_type="ETF"))

        # Watchlists menu
        watchlist_menu = menubar.addMenu("Watchlists")

        stocks_watchlist_action = watchlist_menu.addAction("Stocks")
        stocks_watchlist_action.setObjectName("action_stocks_watchlist")
        stocks_watchlist_action.triggered.connect(self.setCurrentPage(StocksWatchlistPage))

        futures_watchlist_action = watchlist_menu.addAction("Futures")
        futures_watchlist_action.setObjectName("action_futures_watchlist")
        futures_watchlist_action.triggered.connect(self.setCurrentPage(FuturesWatchlistPage))

        etf_watchlist_action = watchlist_menu.addAction("ETF")
        etf_watchlist_action.setObjectName("action_etf_watchlist")
        etf_watchlist_action.triggered.connect(self.setCurrentPage(ETFWatchlistPage))

    def setCurrentPage(
        self, page_class: Type[BaseView], **kwargs: Any
    ) -> Callable[[], None]:
        """HOF for page navigation."""
        def set_page() -> None:
            if self._current_page is not None:
                self.page_container.removeWidget(self._current_page)
                self._current_page.onDestroy()
                self._current_page.deleteLater()

            if kwargs:
                self._current_page = page_class(**kwargs)
            else:
                self._current_page = page_class()

            self.page_container.addWidget(self._current_page)
            self.page_container.setCurrentWidget(self._current_page)

            log.info(f"Switched to page: {page_class.__name__}")

        return set_page

    def _quit_application(self) -> None:
        """Quit the application."""
        log.info("Quit requested")
        self.close()

    def closeEvent(self, event: Any) -> None:
        """Handle window close event."""
        log.info("MainWindow closing...")

        # Stop market timer
        if hasattr(self, '_market_timer'):
            self._market_timer.stop()

        # Destroy current page first
        if self._current_page is not None:
            self._current_page.onDestroy()
            self._current_page = None

        # Shutdown application bootstrap
        try:
            app = get_app()
            app.shutdown()
        except Exception as e:
            log.error(f"Error during shutdown: {e}")

        log.info("MainWindow closed")

        # Accept the event to allow window to close
        event.accept()

        # Quit the Qt application
        QApplication.instance().quit()

    def __del__(self):
        log.debug("MainWindow deleted")
