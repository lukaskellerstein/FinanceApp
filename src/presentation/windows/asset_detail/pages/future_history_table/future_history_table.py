"""
Future History Table Page - displays historical data for futures in a tabbed table format.

Shows each contract (subsymbol) in a separate tab, allowing easy comparison
of different futures contracts for the same underlying asset.
"""

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset
from src.domain.entities.timeframe import TimeFrame
from src.presentation.core.base_view import BaseView
from src.ui.components.historical_data_table.table import HistoricalDataTable

log = logging.getLogger("CellarLogger")


class ContractTab(QWidget):
    """
    A tab widget for a single futures contract.

    Contains the contract info and historical data table.
    """

    def __init__(
        self,
        contract_symbol: str,
        local_symbol: str,
        last_trade_date: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.contract_symbol = contract_symbol
        self.local_symbol = local_symbol
        self.last_trade_date = last_trade_date
        self.table: Optional[HistoricalDataTable] = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Info labels
        self.info_label = QLabel(f"Contract: {local_symbol} | Expires: {last_trade_date}")
        self.info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        self.layout.addWidget(self.info_label)

        # Stats labels
        self.stats_layout = QVBoxLayout()
        self.from_label = QLabel("From: --")
        self.to_label = QLabel("To: --")
        self.bar_count_label = QLabel("Bars: 0")
        self.stats_layout.addWidget(self.from_label)
        self.stats_layout.addWidget(self.to_label)
        self.stats_layout.addWidget(self.bar_count_label)
        self.layout.addLayout(self.stats_layout)

    def set_data(self, data) -> int:
        """
        Set the data for this contract tab.

        Returns:
            Number of bars in the data
        """
        if data is not None and not data.empty:
            data = data.sort_index()

            bar_count = data.shape[0]
            self.bar_count_label.setText(f"Bars: {bar_count}")
            self.from_label.setText(
                f"From: {data.head(1).index[0].strftime('%Y-%m-%d %H:%M:%S')}"
            )
            self.to_label.setText(
                f"To: {data.tail(1).index[0].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            if self.table is not None:
                self.table.setData(data)
            else:
                self.table = HistoricalDataTable(data)
                self.layout.addWidget(self.table)

            return bar_count
        else:
            self.bar_count_label.setText("Bars: 0")
            self.from_label.setText("From: No data")
            self.to_label.setText("To: No data")

            if self.table is not None:
                self.table.setData(None)
            else:
                self.table = HistoricalDataTable(None)
                self.layout.addWidget(self.table)

            return 0


class FutureHistoryTablePage(BaseView):
    """
    Page for displaying futures historical data in a tabbed table format.

    Features:
    - Tab widget with a tab for each contract (subsymbol)
    - Each tab shows the historical data table for that contract
    - Update/Download buttons for all contracts
    - Progress bar for download operations
    """

    # Tell BaseView where to find UI/QSS files
    ui_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "future_history_table.ui"
    )
    qss_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "history_table",
        "history_table.qss",
    )

    # Qt signal for thread-safe progress updates from background threads
    progressSignal = pyqtSignal(float)

    subscriptions = []
    lock = threading.Lock()

    asset: Asset
    timeframe: TimeFrame
    contract_tabs: Dict[str, ContractTab]

    def __init__(self, **kwargs: Any):
        super().__init__()
        self.setObjectName("future_history_table_page")
        log.info("FutureHistoryTablePage initializing...")

        # Apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # Default timeframe
        self.timeframe = TimeFrame.DAY_1

        # Contract tabs dictionary
        self.contract_tabs: Dict[str, ContractTab] = {}

        # Signals
        self.updateButton.clicked.connect(self._update_data)
        self.downloadButton.clicked.connect(self._download_data)
        self.progressSignal.connect(self._update_progress)

        self.progressBar.hide()
        self._update_progress(0)

        self._current_download = None
        self._init_contract_tabs()

    def _init_contract_tabs(self) -> None:
        """Initialize tabs for each contract."""
        self._build_tabs()

    def _build_tabs(self) -> None:
        """Build or rebuild tabs for all contracts."""
        log.info(f"Building tabs for {len(self.asset.contract_details)} contracts...")

        app = get_app()
        total_bars = 0
        contract_count = 0

        # Clear existing tabs
        self.contractTabWidget.clear()
        self.contract_tabs.clear()

        # Sort contracts by last_trade_date
        sorted_contracts = sorted(
            self.asset.contract_details,
            key=lambda cd: getattr(cd.contract, "last_trade_date", ""),
            reverse=True,  # Most recent first
        )

        for cd in sorted_contracts:
            contract = cd.contract
            local_symbol = getattr(contract, "local_symbol", "")
            last_trade_date = getattr(contract, "last_trade_date", "")

            if not local_symbol or not last_trade_date:
                continue

            # Build the compound symbol
            contract_symbol = f"{local_symbol}-{last_trade_date}"

            # Create tab for this contract
            tab = ContractTab(
                contract_symbol=contract_symbol,
                local_symbol=local_symbol,
                last_trade_date=last_trade_date,
            )

            # Load data for this contract
            data = app.historical_data_service.get_historical_data(
                contract_symbol, self.timeframe.value
            )
            bar_count = tab.set_data(data)
            total_bars += bar_count
            contract_count += 1

            # Add tab to tab widget
            tab_title = f"{local_symbol} ({last_trade_date[:6]})"
            self.contractTabWidget.addTab(tab, tab_title)

            # Store reference
            self.contract_tabs[contract_symbol] = tab

        # Update summary labels
        self.contractCountLabel.setText(f"{contract_count} contracts")
        self.totalBarsLabel.setText(f"[{total_bars} total bars]")

        # Enable/disable buttons based on data availability
        self.updateButton.setDisabled(total_bars == 0)

    def refresh(self, asset: Asset) -> None:
        """
        Refresh the page with updated asset data.

        Called when contracts are added or removed.

        Args:
            asset: The updated asset with new contract list
        """
        log.info(f"Refreshing FutureHistoryTablePage for {asset.symbol}...")
        self.asset = asset
        self._build_tabs()

    def _reload_all_data(self) -> None:
        """Reload data for all contract tabs."""
        app = get_app()
        total_bars = 0

        for contract_symbol, tab in self.contract_tabs.items():
            data = app.historical_data_service.get_historical_data(
                contract_symbol, self.timeframe.value
            )
            bar_count = tab.set_data(data)
            total_bars += bar_count

        self.totalBarsLabel.setText(f"[{total_bars} total bars]")
        self.updateButton.setDisabled(total_bars == 0)

    @pyqtSlot()
    def _update_data(self) -> None:
        """Update historical data for all contracts (incremental download)."""
        self.statusLabel.setText("Updating...")
        self.statusLabel.setStyleSheet("color: #2196F3;")  # Blue
        self.progressBar.show()
        self._update_progress(0)

        app = get_app()
        progress = app.historical_data_service.update_historical_data(
            assets=[self.asset],
            timeframe=self.timeframe.value,
        )

        # Connect to progress signals
        progress.progress_changed.connect(self._on_progress_changed)
        progress.completed.connect(self._on_update_completed)
        progress.error.connect(self._on_download_error)

        self._current_download = progress

    @pyqtSlot()
    def _download_data(self) -> None:
        """Download historical data for all contracts (full download)."""
        self.statusLabel.setText("Downloading...")
        self.statusLabel.setStyleSheet("color: #2196F3;")  # Blue
        self.progressBar.show()
        self._update_progress(0)

        app = get_app()
        progress = app.historical_data_service.download_historical_data(
            assets=[self.asset],
            timeframe=self.timeframe.value,
        )

        # Connect to progress signals
        progress.progress_changed.connect(self._on_progress_changed)
        progress.completed.connect(self._on_download_completed)
        progress.error.connect(self._on_download_error)

        self._current_download = progress

    @pyqtSlot(float)
    def _on_progress_changed(self, value: float) -> None:
        """Handle progress change from download service."""
        self.progressSignal.emit(value)

    @pyqtSlot()
    def _on_update_completed(self) -> None:
        """Handle update completion."""
        self.statusLabel.setText("Update complete")
        self.statusLabel.setStyleSheet("color: #4CAF50;")  # Green
        self.progressSignal.emit(100.0)

    @pyqtSlot()
    def _on_download_completed(self) -> None:
        """Handle download completion."""
        self.statusLabel.setText("Download complete")
        self.statusLabel.setStyleSheet("color: #4CAF50;")  # Green
        self.progressSignal.emit(100.0)

    @pyqtSlot(str)
    def _on_download_error(self, error: str) -> None:
        """Handle download error."""
        log.error(f"Download error: {error}")
        self.statusLabel.setText(f"Error: {error}")
        self.statusLabel.setStyleSheet("color: #F44336;")  # Red
        self.progressBar.hide()

    @pyqtSlot(float)
    def _update_progress(self, value: float) -> None:
        """Update progress bar (thread-safe)."""
        with self.lock:
            log.debug(f"Progress: {value}%")
            self.progressBar.setValue(int(value))

            if value >= 100:
                self.progressBar.hide()
                self._reload_all_data()

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("FutureHistoryTablePage destroying...")

        # Cancel any running download
        if self._current_download:
            app = get_app()
            app.historical_data_service.cancel_download()

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("FutureHistoryTablePage deleted")
