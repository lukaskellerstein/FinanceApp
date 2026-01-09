"""
Future History Chart Page - displays historical data for futures as a multi-candlestick chart.

Shows multiple contract months overlaid on the same chart, allowing comparison
of different futures contracts (subsymbols) for the same underlying asset.

Adapted from the old src/ui/windows/asset_detail/futures/pages/history_chart/history_chart.py
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
from src.ui.components.multi_candlestick_chart.chart import MyMultiCandlestickChart
from src.presentation.windows.asset_detail.pages.history_chart.helpers import (
    fillGapsInDays,
    plotMonths,
    plotQuarters,
    plotSeasons,
    plotUSHolidays,
    plotWeekends,
    plotWeeks,
    plotYears,
)

log = logging.getLogger("CellarLogger")


class FutureHistoryChartPage(BaseView):
    """
    Page for displaying futures historical data as a multi-candlestick chart.

    Features:
    - Displays multiple contract months (subsymbols) overlaid on the same chart
    - Duration selector for zoom level
    - Overlay checkboxes (US Holidays, Weeks, Months, etc.)
    - Interactive candlestick chart with volume
    - Shows expiration dates for each contract
    - Download/Update button to fetch data for all contracts
    """

    # Signals
    downloadCompleted = pyqtSignal()

    asset: Asset

    originData: pd.DataFrame
    dataDF: pd.DataFrame
    datesDF: pd.DataFrame

    currentRange: Tuple[int, int]
    candlestickChart: Optional[MyMultiCandlestickChart]
    lock = threading.Lock()

    # Tell BaseView where to find UI/QSS files (reuse existing history_chart UI)
    ui_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "history_chart",
        "history_chart.ui",
    )
    qss_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "history_chart",
        "history_chart.qss",
    )

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("FutureHistoryChartPage initializing...")

        # Apply styles attribute
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # DEFAULTS
        self.currentRange = (0, 0)
        self.timeframe = TimeFrame.DAY_1
        self.duration = "1 year"  # Match combo box text
        self.candlestickChart = None
        self.dataDF = None
        self.datesDF = None
        self.dataDF_flat = None

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

        # Hide loading progress bar initially (shown during download)
        self.loadingProgressBar.hide()

        # Update button setup
        self.updateButton.clicked.connect(self._update_or_download_data)
        self.downloadCompleted.connect(self._on_download_completed)
        self._current_download = None
        self._has_data = False

        # Init chart
        self._init_chart()

        self.durationComboBox.setCurrentText(self.duration)

    def _init_chart(self) -> None:
        """Initialize the multi-candlestick chart with historical data from all contracts."""
        log.info("Loading historical data for all contracts...")
        start = time.time()

        # Collect all data from all contracts
        data_frames = []

        app = get_app()

        log.info(f"Asset has {len(self.asset.contract_details)} contract details")

        # Iterate through all contract details
        for cd in self.asset.contract_details:
            contract = cd.contract

            # Build the compound symbol: localSymbol-lastTradeDate
            local_symbol = getattr(contract, "local_symbol", "")
            last_trade_date = getattr(contract, "last_trade_date", "")

            log.info(f"Contract: local_symbol={local_symbol}, last_trade_date={last_trade_date}")

            if not local_symbol or not last_trade_date:
                log.warning(f"Skipping contract with missing symbol info")
                continue

            # Flat symbol format: local_symbol-last_trade_date
            full_symbol_name = f"{local_symbol}-{last_trade_date}"
            log.info(f"Loading data for contract: {full_symbol_name}")

            try:
                histData = app.historical_data_service.get_historical_data(
                    full_symbol_name, self.timeframe.value
                )

                if histData is not None and not histData.empty:
                    log.info(f"Got {len(histData)} rows for {full_symbol_name}")
                    histData = fillGapsInDays(histData, self.timeframe)
                    histData["LocalSymbol"] = local_symbol
                    histData["LastTradeDate"] = last_trade_date
                    histData = histData.reset_index()
                    log.info(f"After processing, columns: {histData.columns.tolist()}")

                    data_frames.append(histData)
                else:
                    log.warning(f"No data found for {full_symbol_name}")
            except Exception as e:
                log.error(f"Error loading data for {full_symbol_name}: {e}")

        # Concatenate all data frames at once
        if data_frames:
            allHistData = pd.concat(data_frames, ignore_index=True)
        else:
            allHistData = pd.DataFrame()

        end = time.time()
        log.info(f"Loading all contract data takes: {end - start} sec.")
        log.info(f"Total rows in allHistData: {len(allHistData)}")
        if len(allHistData) > 0:
            log.info(f"Columns in allHistData: {allHistData.columns.tolist()}")

        if len(allHistData) > 0:
            self._has_data = True
            self.updateButton.setText("↻ Update")

            # Create dates lookup dataframe
            datesDf = pd.DataFrame(
                data=allHistData.groupby("Datetime").groups.keys(),
                columns=["Datetime"],
            )
            datesDf["id"] = np.arange(datesDf.shape[0])
            datesDf = datesDf.set_index("Datetime")

            # Assign IDs based on date lookup
            allHistData["id"] = allHistData.apply(
                lambda x: self._fill_id(x, datesDf), axis=1
            )

            self.dataDF = allHistData.copy()
            self.originData = allHistData.copy()
            self.datesDF = datesDf.copy()

            # Create flattened dataframe for overlay plotting
            self.dataDF_flat = (
                allHistData.sort_values("LastTradeDate")
                .groupby(["Datetime"])
                .first()
            )

            # Plot the candlestick chart
            start = time.time()
            self._plot_candlestick_chart(
                self.dataDF, self.datesDF, duration=self.duration
            )
            end = time.time()
            log.info(f"plotCandlestickChart takes: {end - start} sec.")
        else:
            self._has_data = False
            self.updateButton.setText("↓ Download")

            # Show message when no data available
            noDataLabel = QLabel(
                "No historical data available for futures contracts.\n"
                "Click 'Download' button to fetch data."
            )
            noDataLabel.setStyleSheet("color: gray; font-size: 14px; padding: 20px;")
            self.chartBox.addWidget(noDataLabel)

    def _fill_id(self, row: pd.Series, dates: pd.DataFrame) -> int:
        """Get the ID for a row based on its datetime."""
        try:
            return dates.index.get_loc(row["Datetime"])
        except KeyError:
            return -1

    def _plot_candlestick_chart(
        self, data: pd.DataFrame, dates: pd.DataFrame, **kwargs: Any
    ) -> None:
        """Create and display the multi-candlestick chart."""
        chart_range = (0, 0)
        if "duration" in kwargs:
            chart_range = self._get_duration_range(kwargs["duration"])
        elif "range" in kwargs:
            chart_range = kwargs["range"]

        self.candlestickChart = MyMultiCandlestickChart(data, dates, chart_range)
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

        if self.dataDF is not None and self.candlestickChart is not None:
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
            plotUSHolidays(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _weeks_checkbox_changed(self, state: int) -> None:
        """Handle weeks checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotWeeks(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _months_checkbox_changed(self, state: int) -> None:
        """Handle months checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotMonths(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _seasons_checkbox_changed(self, state: int) -> None:
        """Handle seasons checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotSeasons(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _quarters_checkbox_changed(self, state: int) -> None:
        """Handle quarters checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotQuarters(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    @pyqtSlot(int)
    def _years_checkbox_changed(self, state: int) -> None:
        """Handle years checkbox change."""
        if state == Qt.CheckState.Checked.value:
            plotYears(self.dataDF_flat, self.candlestickChart.candlestickPlot)
        else:
            self._redraw_chart()

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _redraw_chart(self) -> None:
        """Redraw the chart with current checkbox states."""
        self._plot_candlestick_chart(
            self.originData, self.datesDF, range=self.currentRange
        )

        if self.usHolidaysCheckBox.isChecked():
            plotUSHolidays(
                self.dataDF_flat, self.candlestickChart.candlestickPlot
            )

        if self.weeksCheckbox.isChecked():
            plotWeeks(self.dataDF_flat, self.candlestickChart.candlestickPlot)

        if self.monthsCheckbox.isChecked():
            plotMonths(self.dataDF_flat, self.candlestickChart.candlestickPlot)

        if self.seasonsCheckbox.isChecked():
            plotSeasons(self.dataDF_flat, self.candlestickChart.candlestickPlot)

        if self.quartersCheckbox.isChecked():
            plotQuarters(
                self.dataDF_flat, self.candlestickChart.candlestickPlot
            )

        if self.yearsCheckbox.isChecked():
            plotYears(self.dataDF_flat, self.candlestickChart.candlestickPlot)

    # --------------------------------------------------------
    # Download/Update Data
    # --------------------------------------------------------

    @pyqtSlot()
    def _update_or_download_data(self) -> None:
        """Update or download historical data for all contracts."""
        self.updateButton.setEnabled(False)
        if self._has_data:
            self.updateButton.setText("↻ Updating...")
        else:
            self.updateButton.setText("↓ Downloading...")
        self.loadingProgressBar.show()

        app = get_app()

        if self._has_data:
            progress = app.historical_data_service.update_historical_data(
                assets=[self.asset],
                timeframe=self.timeframe.value,
            )
        else:
            progress = app.historical_data_service.download_historical_data(
                assets=[self.asset],
                timeframe=self.timeframe.value,
            )

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
        log.info("Download completed, reloading futures chart...")
        self.updateButton.setEnabled(True)
        self.loadingProgressBar.hide()

        # Clear existing chart
        if self.candlestickChart is not None:
            self.chartBox.removeWidget(self.candlestickChart)
            self.candlestickChart.onDestroy()
            self.candlestickChart.deleteLater()
            self.candlestickChart = None

        # Clear no-data label if present
        for i in reversed(range(self.chartBox.count())):
            widget = self.chartBox.itemAt(i).widget()
            if widget is not None and isinstance(widget, QLabel):
                self.chartBox.removeWidget(widget)
                widget.deleteLater()

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
        max_index = self.dataDF["id"].max() if self.dataDF is not None else 0

        if min_val is not None and self.dataDF is not None:
            temp_df = self.dataDF[self.dataDF["Datetime"] > min_val]
            if temp_df.shape[0] > 0:
                min_index = temp_df["id"].min()

        return (min_index, max_index)

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self) -> None:
        """Custom destroy method."""
        log.info("FutureHistoryChartPage destroying...")

        # Cancel any running download
        if self._current_download:
            app = get_app()
            app.historical_data_service.cancel_download()

        if self.candlestickChart is not None:
            self.candlestickChart.onDestroy()

    def __del__(self) -> None:
        """Python destructor."""
        log.debug("FutureHistoryChartPage deleted")
