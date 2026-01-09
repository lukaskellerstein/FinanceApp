"""
History Table Page - displays historical data in a table format.

Adapted from the old src/ui/windows/asset_detail/shared/pages/history_table/history_table.py
to work with the new Clean Architecture.
"""

import logging
import os
import threading
from typing import Any, Optional

from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset
from src.domain.entities.timeframe import TimeFrame
from src.presentation.core.base_view import BaseView
from src.ui.components.historical_data_table.table import HistoricalDataTable

log = logging.getLogger("CellarLogger")


class HistoryTablePage(BaseView):
    """
    Page for displaying historical data in a table.

    Features:
    - Update/Download buttons with progress bar
    - Data info: From date, To date, Bar count
    - Table view of OHLCV data
    """

    # Tell BaseView where to find UI/QSS files
    ui_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_table.ui")
    qss_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_table.qss")

    # Qt signal for thread-safe progress updates from background threads
    progressSignal = pyqtSignal(float)

    subscriptions = []
    lock = threading.Lock()

    asset: Asset
    timeframe: TimeFrame

    def __init__(self, **kwargs: Any):
        super().__init__()
        self.setObjectName("history_table_page")
        log.info("HistoryTablePage initializing...")

        # Apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # Default timeframe
        self.timeframe = TimeFrame.DAY_1

        # Signals
        self.updateButton.clicked.connect(self._update_data)
        self.downloadButton.clicked.connect(self._download_data)
        self.progressSignal.connect(self._update_progress)

        self.progressBar.hide()
        self._update_progress(0)

        self.table: Optional[HistoricalDataTable] = None
        self._current_download = None
        self._load_hist_data()

    def _load_hist_data(self) -> None:
        """Load historical data from database."""
        app = get_app()
        self.data = app.historical_data_service.get_historical_data(
            self.asset.symbol, self.timeframe.value
        )

        if self.data is not None and not self.data.empty:
            self.data = self.data.sort_index()

            self.barCountLabel.setText(str(self.data.shape[0]))
            self.fromLabel.setText(
                self.data.head(1).index[0].strftime("%Y%m%d %H:%M:%S")
            )
            self.toLabel.setText(
                self.data.tail(1).index[0].strftime("%Y%m%d %H:%M:%S")
            )

            self.updateButton.setDisabled(False)

            if self.table is not None:
                self.table.setData(self.data)
            else:
                self.table = HistoricalDataTable(self.data)
                self.gridLayout_2.addWidget(self.table, 3, 0, 1, 2)
        else:
            self.barCountLabel.setText("0")
            self.fromLabel.setText("No data")
            self.toLabel.setText("No data")

            self.updateButton.setDisabled(True)

            if self.table is not None:
                self.table.setData(None)
            else:
                self.table = HistoricalDataTable(None)
                self.gridLayout_2.addWidget(self.table, 3, 0, 1, 2)

    @pyqtSlot()
    def _update_data(self) -> None:
        """Update historical data (incremental download)."""
        self.progressBar.show()
        self._update_progress(0)

        app = get_app()
        progress = app.historical_data_service.update_historical_data(
            assets=[self.asset],
            timeframe=self.timeframe.value,
        )

        # Connect to progress signals
        progress.progress_changed.connect(self._on_progress_changed)
        progress.completed.connect(self._on_download_completed)
        progress.error.connect(self._on_download_error)

        self._current_download = progress

    @pyqtSlot()
    def _download_data(self) -> None:
        """Download historical data (full download)."""
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
    def _on_download_completed(self) -> None:
        """Handle download completion."""
        self.progressSignal.emit(100.0)

    @pyqtSlot(str)
    def _on_download_error(self, error: str) -> None:
        """Handle download error."""
        log.error(f"Download error: {error}")
        self.progressBar.hide()

    @pyqtSlot(float)
    def _update_progress(self, value: float) -> None:
        """Update progress bar (thread-safe)."""
        with self.lock:
            log.debug(f"Progress: {value}%")
            self.progressBar.setValue(int(value))

            if value >= 100:
                self.progressBar.hide()
                self._load_hist_data()

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("HistoryTablePage destroying...")

        # Cancel any running download
        if self._current_download:
            app = get_app()
            app.historical_data_service.cancel_download()

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("HistoryTablePage deleted")
