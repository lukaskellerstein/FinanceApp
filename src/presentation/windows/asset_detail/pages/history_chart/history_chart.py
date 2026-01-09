"""
History Chart Page - displays historical data as a candlestick chart.

Adapted from the old src/ui/windows/asset_detail/shared/pages/history_chart/history_chart.py
to work with the new Clean Architecture.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtWidgets import QLabel

from src.application.bootstrap import get_app
from src.domain.entities.asset import Asset
from src.domain.entities.timeframe import TimeFrame, Duration
from src.presentation.core.base_view import BaseView
from src.ui.components.candlestick_chart.chart import MyCandlestickChart
from src.presentation.windows.asset_detail.pages.history_chart.helpers import (
    fillGapsInDays,
    hasDecadeOfData,
    plotDecades,
    plotMonths,
    plotQuarters,
    plotSeasons,
    plotUSHolidays,
    plotWeekends,
    plotWeeks,
    plotYears,
)

log = logging.getLogger("CellarLogger")


class HistoryChartPage(BaseView):
    """
    Page for displaying historical data as a candlestick chart.

    Features:
    - Duration selector for zoom level
    - Overlay checkboxes (US Holidays, Weeks, Months, etc.)
    - Interactive candlestick chart with volume
    - Update/Download button for data management
    """

    asset: Asset

    originData: pd.DataFrame
    dataDF: pd.DataFrame

    currentRange: Tuple[int, int]
    candlestickChart: Optional[MyCandlestickChart]

    # Tell BaseView where to find UI/QSS files
    ui_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_chart.ui")
    qss_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history_chart.qss")

    # Qt signal for thread-safe updates from background threads
    downloadCompleted = pyqtSignal()

    lock = threading.Lock()

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("HistoryChartPage initializing...")

        # Apply styles attribute
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # DEFAULTS
        self.currentRange = (0, 0)
        self.timeframe = TimeFrame.DAY_1
        self.duration = "1 year"  # Match combo box text
        self.candlestickChart = None
        self.data = None

        # Signals
        self.durationComboBox.currentTextChanged.connect(
            self._duration_combo_box_changed
        )
        self.usHolidaysCheckBox.stateChanged.connect(
            self._us_holidays_checkbox_changed
        )
        self.weeksCheckbox.stateChanged.connect(self._weeks_checkbox_changed)
        self.monthsCheckbox.stateChanged.connect(self._months_checkbox_changed)
        self.seasonsCheckbox.stateChanged.connect(self._seasons_checkbox_changed)
        self.quartersCheckbox.stateChanged.connect(
            self._quarters_checkbox_changed
        )
        self.yearsCheckbox.stateChanged.connect(self._years_checkbox_changed)
        self.decadesCheckbox.stateChanged.connect(self._decades_checkbox_changed)

        # Update button
        self.updateButton.clicked.connect(self._update_or_download_data)
        self.downloadCompleted.connect(self._on_download_completed)
        self._current_download = None
        self._has_data = False

        # Hide loading progress bar initially
        self.loadingProgressBar.hide()

        # Init chart
        self._init_chart()

        self.durationComboBox.setCurrentText(self.duration)

    def _init_chart(self) -> None:
        """Initialize the candlestick chart with historical data."""
        # Get historical data from service
        log.info("Loading historical data...")
        start = time.time()
        self.data = self._get_hist_data(self.asset.symbol, self.timeframe)
        end = time.time()
        log.info(f"Get data takes: {end - start} sec.")

        # Fill gaps in data
        log.info("Filling gaps in data...")
        start = time.time()
        if self.data is not None:
            self.data = fillGapsInDays(self.data, self.timeframe)
        end = time.time()
        log.info(f"Enhance data takes: {end - start} sec.")

        if self.data is not None and not self.data.empty:
            self.data["id"] = np.arange(self.data.shape[0])
            self._has_data = True
            self.updateButton.setText("↻ Update")

            # Enable/disable decades checkbox based on data availability
            has_decade = hasDecadeOfData(self.data)
            self.decadesCheckbox.setEnabled(has_decade)

            # Create candlestick chart
            start = time.time()
            self.originData = self.data.copy()
            self._plot_candlestick_chart(self.data, duration=self.duration)
            end = time.time()
            log.info(f"plotCandlestickChart takes: {end - start} sec.")
        else:
            self._has_data = False
            self.updateButton.setText("↓ Download")

            # Show message when no data available
            noDataLabel = QLabel("No historical data available. Click Download to get data.")
            noDataLabel.setStyleSheet("color: gray; font-size: 14px; padding: 20px;")
            self.chartBox.addWidget(noDataLabel)

    def _get_hist_data(self, symbol: str, timeframe: TimeFrame) -> Optional[pd.DataFrame]:
        """Get historical data from database."""
        start = time.time()
        app = get_app()
        data = app.historical_data_service.get_historical_data(symbol, timeframe.value)
        if data is not None:
            data = data.sort_index()
        end = time.time()
        log.info(f"Database query takes {end - start} sec.")
        return data

    def _plot_candlestick_chart(self, data: pd.DataFrame, **kwargs: Any) -> None:
        """Create and display the candlestick chart."""
        chart_range = (0, 0)
        if "duration" in kwargs:
            chart_range = self._get_duration_range(kwargs["duration"])
        elif "range" in kwargs:
            chart_range = kwargs["range"]

        self.candlestickChart = MyCandlestickChart(data, chart_range)
        self.candlestickChart.on_range_update.connect(self._update_range)
        self.chartBox.addWidget(self.candlestickChart, 0, 0, 0, 0)

    # --------------------------------------------------------
    # COMBO-BOXES
    # --------------------------------------------------------

    @pyqtSlot(str)
    def _duration_combo_box_changed(self, value: str) -> None:
        """Handle duration combo box change."""
        log.info(f"Duration changed to: {value}")
        start = time.time()

        self.duration = value

        if self.data is not None and self.candlestickChart is not None:
            chart_range = self._get_duration_range(value)
            self.candlestickChart.overviewPlot.timeRegion.setRegion(chart_range)
            # Manually emit signal since setRegion() doesn't trigger sigRegionChangeFinished
            self.candlestickChart.overviewPlot.timeRegion.sigRegionChangeFinished.emit(
                self.candlestickChart.overviewPlot.timeRegion
            )

        end = time.time()
        log.info(f"Duration change takes: {end - start} sec.")

    # --------------------------------------------------------
    # CHECK-BOXES
    # --------------------------------------------------------

    @pyqtSlot(int)
    def _us_holidays_checkbox_changed(self, state: int) -> None:
        """Handle US holidays checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotUSHolidays(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _weeks_checkbox_changed(self, state: int) -> None:
        """Handle weeks checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotWeeks(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _months_checkbox_changed(self, state: int) -> None:
        """Handle months checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotMonths(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _seasons_checkbox_changed(self, state: int) -> None:
        """Handle seasons checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotSeasons(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _quarters_checkbox_changed(self, state: int) -> None:
        """Handle quarters checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotQuarters(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _years_checkbox_changed(self, state: int) -> None:
        """Handle years checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotYears(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _decades_checkbox_changed(self, state: int) -> None:
        """Handle decades checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotDecades(self.data, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    # --------------------------------------------------------
    # UPDATE / DOWNLOAD
    # --------------------------------------------------------

    @pyqtSlot()
    def _update_or_download_data(self) -> None:
        """Update or download historical data based on current state."""
        self.updateButton.setEnabled(False)
        if self._has_data:
            self.updateButton.setText("↻ Updating...")
        else:
            self.updateButton.setText("↓ Downloading...")
        self.loadingProgressBar.show()

        app = get_app()

        if self._has_data:
            # Update existing data
            progress = app.historical_data_service.update_historical_data(
                assets=[self.asset],
                timeframe=self.timeframe.value,
            )
        else:
            # Download new data
            progress = app.historical_data_service.download_historical_data(
                assets=[self.asset],
                timeframe=self.timeframe.value,
            )

        # Connect to progress signals
        progress.completed.connect(self._on_download_signal)
        progress.error.connect(self._on_download_error)

        self._current_download = progress

    @pyqtSlot()
    def _on_download_signal(self) -> None:
        """Handle download completion signal (may be from background thread)."""
        self.downloadCompleted.emit()

    @pyqtSlot()
    def _on_download_completed(self) -> None:
        """Handle download completion (UI thread)."""
        log.info("Download completed, reloading chart...")
        self.updateButton.setEnabled(True)
        self.loadingProgressBar.hide()

        # Clear existing chart
        if self.candlestickChart is not None:
            self.chartBox.removeWidget(self.candlestickChart)
            self.candlestickChart.onDestroy()
            self.candlestickChart.deleteLater()
            self.candlestickChart = None

        # Reload chart with new data
        self._init_chart()

    @pyqtSlot(str)
    def _on_download_error(self, error: str) -> None:
        """Handle download error."""
        log.error(f"Download error: {error}")
        self.updateButton.setEnabled(True)
        self.loadingProgressBar.hide()
        if self._has_data:
            self.updateButton.setText("↻ Update")
        else:
            self.updateButton.setText("↓ Download")

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _redraw_chart(self) -> None:
        """Redraw the chart with current checkbox states."""
        self._plot_candlestick_chart(self.originData, range=self.currentRange)

        if self.usHolidaysCheckBox.isChecked():
            plotUSHolidays(
                self.originData, self.candlestickChart.candlestickPlot
            )

        if self.weeksCheckbox.isChecked():
            plotWeeks(self.originData, self.candlestickChart.candlestickPlot)

        if self.monthsCheckbox.isChecked():
            plotMonths(self.originData, self.candlestickChart.candlestickPlot)

        if self.seasonsCheckbox.isChecked():
            plotSeasons(self.originData, self.candlestickChart.candlestickPlot)

        if self.quartersCheckbox.isChecked():
            plotQuarters(
                self.originData, self.candlestickChart.candlestickPlot
            )

        if self.yearsCheckbox.isChecked():
            plotYears(self.originData, self.candlestickChart.candlestickPlot)

        if self.decadesCheckbox.isChecked():
            plotDecades(self.originData, self.candlestickChart.candlestickPlot)

    def _update_range(self, chart_range: Tuple[int, int]) -> None:
        """Update current range from chart."""
        self.currentRange = chart_range

    def _get_duration_range(self, duration: str) -> Tuple[int, int]:
        """Convert duration string to data index range."""
        # Use timezone-aware datetime to match the data index
        max_val = datetime.now(timezone.utc)
        min_val = max_val

        # Map duration strings to relativedelta
        if duration == Duration.YEARS_20.value or duration == "20 years":
            min_val = max_val - relativedelta(years=20)
        elif duration == Duration.YEARS_10.value or duration == "10 years":
            min_val = max_val - relativedelta(years=10)
        elif duration == Duration.YEARS_5.value or duration == "5 years":
            min_val = max_val - relativedelta(years=5)
        elif duration == Duration.YEAR_1.value or duration == "1 year":
            min_val = max_val - relativedelta(years=1)
        elif duration == Duration.MONTHS_3.value or duration == "1 quarter":
            min_val = max_val - relativedelta(months=3)
        elif duration == Duration.MONTH_1.value or duration == "1 month":
            min_val = max_val - relativedelta(months=1)
        elif duration == Duration.WEEK_1.value or duration == "1 week":
            min_val = max_val - relativedelta(weeks=1)
        elif duration == Duration.ALL.value or duration == "All":
            min_val = None

        min_index = 0
        max_index = self.data.shape[0]

        if min_val is not None:
            temp_df = self.data[self.data.index > min_val]
            if temp_df.shape[0] > 0:
                min_index = self.data.index.get_loc(temp_df.index[0])

        return (min_index, max_index)

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("HistoryChartPage destroying...")

        # Cancel any running download
        if self._current_download:
            app = get_app()
            app.historical_data_service.cancel_download()

        if self.candlestickChart is not None:
            self.candlestickChart.onDestroy()

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("HistoryChartPage deleted")
