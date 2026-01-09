import logging
import time
from typing import Tuple

import numpy as np
import pandas as pd
import pyqtgraph as pg
from holidays import US
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from src.domain.entities.timeframe import TimeFrame
from src.presentation.components.charts.candlestick_chart.candlestick_plot import CandlestickPlot
from src.presentation.components.charts.candlestick_chart.candlestick_x import CandlesticXAxis
from src.presentation.components.charts.candlestick_chart.overview_plot import OverviewTimePlot
from src.presentation.components.charts.candlestick_chart.volume_plot import VolumePlot

# create logger
log = logging.getLogger("CellarLogger")


class MyCandlestickChart(pg.GraphicsLayoutWidget):
    lastRange = None

    on_range_update = pyqtSignal(object)

    def __init__(
        self, data: pd.DataFrame, range: Tuple[int, int], parent=None, **kargs,
    ):
        super().__init__(parent=parent, **kargs)

        pg.setConfigOptions(antialias=True)

        self.setBackground(QColor("white"))

        self.holidays = US()

        self.timeSeriesData = data.copy()
        self.data = data.reset_index()

        # LABEL ------------------------------
        self.labelXY = pg.LabelItem(justify="left")
        self.labelXY.setText("")
        self.addItem(self.labelXY, row=0, col=0)

        self.labelOHLC = pg.LabelItem(justify="right")
        self.labelOHLC.setText("")
        self.addItem(self.labelOHLC, row=0, col=1)

        # Statistics label (Return, Daily Return, Variance, StdDev)
        self.labelStats = pg.LabelItem(justify="left")
        self.labelStats.setText("")
        self.addItem(self.labelStats, row=1, col=0, colspan=2)

        self.currentRange = range

        # CHART 1 ----------------------------

        start = time.time()

        date_axis = CandlesticXAxis(
            data=self.timeSeriesData, orientation="bottom",
        )

        self.candlestickPlot = CandlestickPlot(
            self.data, self.currentRange, axisItems={"bottom": date_axis}
        )
        self.candlestickPlot.sigRangeChanged.connect(
            self.__updateCandlestickRegion
        )

        self.addItem(self.candlestickPlot, row=2, col=0, colspan=2, rowspan=2)

        self.proxy = pg.SignalProxy(
            self.candlestickPlot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.mouseMoved,
        )

        # CHART 2 ----------------------------

        volumeXAxis = CandlesticXAxis(
            data=self.timeSeriesData, orientation="bottom",
        )

        self.volumePlot = VolumePlot(
            self.data.index,
            self.data["Volume"],
            self.currentRange,
            axisItems={"bottom": volumeXAxis},
        )

        self.volumePlot.sigRangeChanged.connect(self.__updateVolumeRegion)

        self.addItem(self.volumePlot, row=4, col=0, colspan=2)

        self.proxy2 = pg.SignalProxy(
            self.volumePlot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.mouseMoved2,
        )

        # CHART 3 ----------------------------

        x = self.data.index.to_list()
        y = self.timeSeriesData["Close"].ffill().to_list()

        overviewXAxis = CandlesticXAxis(
            data=self.timeSeriesData, orientation="bottom",
        )

        self.overviewPlot = OverviewTimePlot(
            x, y, axisItems={"bottom": overviewXAxis}
        )
        self.overviewPlot.timeRegion.sigRegionChangeFinished.connect(
            self.__updateOverviewTimeRegion
        )

        self.addItem(self.overviewPlot, row=5, col=0, colspan=2)

        # Set the initial region based on the passed range parameter
        if self.currentRange != (0, 0):
            self.overviewPlot.timeRegion.setRegion(self.currentRange)
            # Trigger the update to sync all chart components
            self.__updateOverviewTimeRegion(self.overviewPlot.timeRegion)
        else:
            # Calculate initial stats for all data
            self._updateStats(0, len(self.data))

        end = time.time()
        log.info(f"plot takes: {end - start} sec.")

    def mouseMoved(self, evt):
        pos = evt[
            0
        ]  ## using signal proxy turns original arguments into a tuple
        if self.candlestickPlot.sceneBoundingRect().contains(pos):
            mousePoint = self.candlestickPlot.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            value = round(mousePoint.y(), 2)
            if index > 0 and index < self.data.shape[0]:
                row = self.data.iloc[index]

                self.labelXY.setText(f"x={row['Datetime']}, y={value}")
                self.labelOHLC.setText(
                    f"O={row['Open']}, H={row['High']}, L={row['Low']}, C={row['Close']}, V={row['Volume']:.0f}"
                )

            self.candlestickPlot.vLine.setPos(mousePoint.x())
            self.candlestickPlot.hLine.setPos(mousePoint.y())
            self.volumePlot.vLine.setPos(mousePoint.x())

    def mouseMoved2(self, evt):
        pos = evt[
            0
        ]  ## using signal proxy turns original arguments into a tuple
        if self.volumePlot.sceneBoundingRect().contains(pos):
            mousePoint = self.volumePlot.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            value = round(mousePoint.y(), 2)
            if index > 0 and index < self.data.shape[0]:
                row = self.data.iloc[index]

                self.labelXY.setText(f"x={row['Datetime']}, y={value}")
                self.labelOHLC.setText(
                    f"O={row['Open']}, H={row['High']}, L={row['Low']}, C={row['Close']}, V={row['Volume']:.0f}"
                )
            self.candlestickPlot.vLine.setPos(mousePoint.x())
            self.volumePlot.vLine.setPos(mousePoint.x())

    def _updateStats(self, minIdx: int, maxIdx: int) -> None:
        """Calculate and update statistics for the visible range."""
        if minIdx >= maxIdx or minIdx < 0:
            self.labelStats.setText("")
            return

        # Get data for visible range
        tempDf = self.data.iloc[minIdx:maxIdx]
        if tempDf.empty or len(tempDf) < 2:
            self.labelStats.setText("")
            return

        try:
            # Get closing prices
            closes = tempDf["Close"].dropna()
            if len(closes) < 2:
                self.labelStats.setText("")
                return

            # Total Return: (end - start) / start * 100
            start_price = closes.iloc[0]
            end_price = closes.iloc[-1]
            total_return = ((end_price - start_price) / start_price) * 100 if start_price != 0 else 0

            # Daily Returns
            daily_returns = closes.pct_change().dropna()

            if len(daily_returns) > 0:
                # Daily Return (average)
                daily_return = daily_returns.mean() * 100

                # Daily Variance
                daily_variance = daily_returns.var() * 100

                # Daily Standard Deviation
                daily_std_dev = daily_returns.std() * 100

                self.labelStats.setText(
                    f"Return: {total_return:+.2f}%  |  "
                    f"Daily Return: {daily_return:+.4f}%  |  "
                    f"Daily Variance: {daily_variance:.4f}%  |  "
                    f"Daily StdDev: {daily_std_dev:.4f}%"
                )
            else:
                self.labelStats.setText(f"Return: {total_return:+.2f}%")

        except Exception as e:
            log.warning(f"Error calculating stats: {e}")
            self.labelStats.setText("")

    def __updateCandlestickRegion(self, window, viewRange):
        xRange = viewRange[0]
        # yRange = viewRange[1]
        self.overviewPlot.timeRegion.setRegion(xRange)

    def __updateVolumeRegion(self, window, viewRange):
        xRange = viewRange[0]
        # yRange = viewRange[1]
        self.overviewPlot.timeRegion.setRegion(xRange)

    def __updateOverviewTimeRegion(self, region):

        region.setZValue(10)
        minX, maxX = region.getRegion()

        # round the values
        minVal = round(minX)
        maxVal = round(maxX)

        log.info(f"set Region: {minVal}, {maxVal}")

        if self.lastRange != (minVal, maxVal):
            self.lastRange = (minVal, maxVal)

            self.on_range_update.emit(self.lastRange)

            log.info(f"run update Range: {minVal}, {maxVal}")

            # Update statistics for visible range
            self._updateStats(minVal, maxVal)

            # udpate X axis of CANDLESTICK
            self.candlestickPlot.updateRange((minVal, maxVal))

            # udpate X axis of Volume
            self.volumePlot.setXRange(minVal, maxVal, padding=0)

            # udpate Y axis of Volume based on visible data
            volMinIdx = max(0, minVal)
            volMaxIdx = min(self.data.shape[0] - 1, maxVal)
            if volMinIdx < volMaxIdx:
                tempDf = self.data.iloc[volMinIdx:volMaxIdx]
                if not tempDf.empty and "Volume" in tempDf.columns:
                    volMin = tempDf["Volume"].min()
                    volMax = tempDf["Volume"].max()
                    if volMin < volMax:
                        self.volumePlot.setYRange(0, volMax, padding=0.1)

            # mi = tempDf["Low"].min()
            # ma = tempDf["High"].max()

            # diff = ((ma - mi) / ma) * 10  # percent

            # update Y axis of Candlestic
            # self.candlestickPlot.setYRange(
            #     # tempDf["Low"].min() - round(diff),
            #     # tempDf["High"].max() + round(diff),
            #     tempDf["Low"].min(),
            #     tempDf["High"].max(),
            #     padding=0,
            # )

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
