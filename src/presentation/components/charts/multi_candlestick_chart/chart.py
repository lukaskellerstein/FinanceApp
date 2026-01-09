import logging
import time
from typing import Tuple
import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor

from src.domain.entities.timeframe import TimeFrame
from src.presentation.components.charts.multi_candlestick_chart.candlestick_plot import (
    CandlestickPlot,
)
from src.presentation.components.charts.candlestick_chart.overview_plot import OverviewTimePlot
from src.presentation.components.charts.multi_candlestick_chart.candlestick_x import CandlesticXAxis

from src.presentation.components.charts.multi_candlestick_chart.helpers import printOHLCInfo
from src.presentation.components.charts.multi_candlestick_chart.volume_plot import VolumePlot

# create logger
log = logging.getLogger("CellarLogger")


class MyMultiCandlestickChart(pg.GraphicsLayoutWidget):
    lastRange = None

    on_range_update = pyqtSignal(object)

    def __init__(
        self,
        dataDF: pd.DataFrame,
        datesDF: pd.DataFrame,
        range: Tuple[int, int],
        parent=None,
        **kargs,
    ):
        super().__init__(parent=parent, **kargs)

        pg.setConfigOptions(antialias=True)

        self.setBackground(QColor("white"))

        # INPUTS
        self.data = dataDF.reset_index()
        self.currentRange = range

        # CHART 1 ----------------------------

        start = time.time()

        date_axis = CandlesticXAxis(data=datesDF, orientation="bottom",)

        self.candlestickPlot = CandlestickPlot(
            self.data, self.currentRange, axisItems={"bottom": date_axis}
        )
        self.candlestickPlot.sigRangeChanged.connect(
            self.__updateCandlestickRegion
        )

        self.addItem(self.candlestickPlot, row=1, col=0, colspan=2, rowspan=1)

        self.proxy = pg.SignalProxy(
            self.candlestickPlot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.mouseMoved,
        )

        # # CHART 2 ----------------------------

        volumeYAxis = pg.AxisItem(orientation="left")
        volumeYAxis.setScale(0.00001)

        volumeXAxis = CandlesticXAxis(data=datesDF, orientation="bottom",)

        self.volumePlot = VolumePlot(
            self.data,
            self.currentRange,
            axisItems={"bottom": volumeXAxis, "left": volumeYAxis},
        )

        self.volumePlot.sigRangeChanged.connect(self.__updateVolumeRegion)

        self.addItem(self.volumePlot, row=3, col=0, colspan=2)

        self.proxy2 = pg.SignalProxy(
            self.volumePlot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self.mouseMoved2,
        )

        # CHART 3 ----------------------------

        x = datesDF["id"].to_list()
        # Only calculate mean on numeric columns to avoid TypeError with string columns
        y = self.data.groupby("Datetime")["Close"].mean().ffill().to_list()

        overviewXAxis = CandlesticXAxis(data=datesDF, orientation="bottom",)

        self.overviewPlot = OverviewTimePlot(
            x, y, axisItems={"bottom": overviewXAxis}
        )
        self.overviewPlot.timeRegion.sigRegionChangeFinished.connect(
            self.__updateOverviewTimeRegion
        )

        self.addItem(self.overviewPlot, row=4, col=0, colspan=2)

        end = time.time()
        log.info(f"plot takes: {end - start} sec.")

    def mouseMoved(self, evt):
        pos = evt[0]
        # print(pos)

        if self.candlestickPlot.sceneBoundingRect().contains(pos):

            mousePoint = self.candlestickPlot.vb.mapSceneToView(pos)

            # set crosshair
            self.candlestickPlot.vLine.setPos(mousePoint.x())
            self.candlestickPlot.hLine.setPos(mousePoint.y())
            self.volumePlot.vLine.setPos(mousePoint.x())

            # other
            index = int(mousePoint.x())
            value = round(mousePoint.y(), 2)
            # print(index)
            # print(value)

            currentBar = self.data.loc[self.data["id"] == index]
            highlighted_group = None  # Track which contract to highlight expiration line for

            # If no data at this position (e.g., hovering in future area beyond data)
            if currentBar.shape[0] == 0:
                max_id = self.data["id"].max()
                if index > max_id:
                    # Find which contract's expiration is closest to (but after) the mouse position
                    exp_positions = self.candlestickPlot.expiration_positions

                    # Find the contract whose expiration is AFTER the mouse position (closest one)
                    closest_group = None
                    closest_pos = float('inf')

                    for group_name, pos_val in exp_positions.items():
                        if pos_val > index:  # Expiration is after mouse position
                            if pos_val < closest_pos:
                                closest_pos = pos_val
                                closest_group = group_name

                    # If no future expiration found, use the one with largest position
                    if closest_group is None:
                        for group_name, pos_val in exp_positions.items():
                            if pos_val > closest_pos or closest_pos == float('inf'):
                                closest_pos = pos_val
                                closest_group = group_name

                    if closest_group:
                        # Extract LocalSymbol from group_name (format: "ESZ4-20241220")
                        parts = closest_group.split('-')
                        local_symbol = parts[0]
                        last_trade_date = parts[1] if len(parts) > 1 else ""

                        # Get the LAST available data for this specific contract
                        contract_data = self.data.loc[
                            (self.data["LocalSymbol"] == local_symbol) &
                            (self.data["LastTradeDate"] == last_trade_date)
                        ]
                        if contract_data.shape[0] > 0:
                            # Get the last row (highest id) for this contract
                            last_id = contract_data["id"].max()
                            currentBar = contract_data.loc[contract_data["id"] == last_id]
                        else:
                            # Fallback to any data at max_id
                            currentBar = self.data.loc[self.data["id"] == max_id]
                        highlighted_group = closest_group
                    else:
                        # Fallback to all data at max_id
                        currentBar = self.data.loc[self.data["id"] == max_id]
            currentBar = currentBar.sort_values(by=["LastTradeDate"])
            # print(currentBar)

            if currentBar.shape[0] > 0:

                # Labels ---
                date = currentBar.iloc[0]["Datetime"]

                resultXHtml = f"<div><span style='color:black'>x={date}</span>, <span style='color:black'>y={value}</span></div>"
                resultOHLCHtml = printOHLCInfo(currentBar)
                self.candlestickPlot.labelOHLC.setHtml(
                    resultXHtml + resultOHLCHtml
                )

                # Opacity for candlestick ---
                validGroupNames = currentBar["LocalSymbol"].unique()
                # print(validGroupNames)

                otherGroups = self.data.loc[
                    ~self.data["LocalSymbol"].isin(
                        validGroupNames
                    )  # ~ is not in
                ]["LocalSymbol"].unique()

                currentGroupIndex = 1
                for vgn in validGroupNames:
                    opacity = 0
                    if currentGroupIndex == 1:
                        opacity = 1
                        # Highlight the expiration line for the first (most prominent) contract
                        if not highlighted_group:
                            # Get the full group name for this contract
                            highlighted_group = f"{vgn}-{currentBar[currentBar['LocalSymbol'] == vgn].iloc[0]['LastTradeDate']}"
                    elif currentGroupIndex == 2:
                        opacity = 0.3
                    elif currentGroupIndex == 3:
                        opacity = 0.2
                    else:
                        opacity = 0.1

                    vgnFullName = f"{vgn}-{currentBar[currentBar['LocalSymbol'] == vgn].iloc[0]['LastTradeDate']}"

                    self.candlestickPlot.setGroupOpacity(vgnFullName, opacity)
                    currentGroupIndex += 1

                # Highlight the expiration line for the selected contract
                if highlighted_group:
                    self.candlestickPlot.setExpirationHighlight(highlighted_group, True)

                for ogn in otherGroups:

                    ognFullName = f"{ogn}-{self.data[self.data['LocalSymbol'] == ogn].iloc[0]['LastTradeDate']}"

                    self.candlestickPlot.setGroupOpacity(ognFullName, 0.02)

    def mouseMoved2(self, evt):
        pos = evt[
            0
        ]  ## using signal proxy turns original arguments into a tuple
        if self.volumePlot.sceneBoundingRect().contains(pos):
            mousePoint = self.volumePlot.vb.mapSceneToView(pos)
            index = int(mousePoint.x())
            value = round(mousePoint.y(), 2)

            currentBar = self.data.loc[self.data["id"] == index]

            # If no data at this position (e.g., hovering in future area beyond data)
            if currentBar.shape[0] == 0:
                max_id = self.data["id"].max()
                if index > max_id:
                    # Find which contract's expiration is closest to (but after) the mouse position
                    exp_positions = self.candlestickPlot.expiration_positions

                    closest_group = None
                    closest_pos = float('inf')

                    for group_name, pos_val in exp_positions.items():
                        if pos_val > index:
                            if pos_val < closest_pos:
                                closest_pos = pos_val
                                closest_group = group_name

                    if closest_group is None:
                        for group_name, pos_val in exp_positions.items():
                            if pos_val > closest_pos or closest_pos == float('inf'):
                                closest_pos = pos_val
                                closest_group = group_name

                    if closest_group:
                        parts = closest_group.split('-')
                        local_symbol = parts[0]
                        last_trade_date = parts[1] if len(parts) > 1 else ""

                        # Get the LAST available data for this specific contract
                        contract_data = self.data.loc[
                            (self.data["LocalSymbol"] == local_symbol) &
                            (self.data["LastTradeDate"] == last_trade_date)
                        ]
                        if contract_data.shape[0] > 0:
                            last_id = contract_data["id"].max()
                            currentBar = contract_data.loc[contract_data["id"] == last_id]
                        else:
                            currentBar = self.data.loc[self.data["id"] == max_id]
                    else:
                        currentBar = self.data.loc[self.data["id"] == max_id]

            currentBar = currentBar.sort_values(by=["LastTradeDate"])

            if currentBar.shape[0] > 0:

                # Labels ---
                date = currentBar.iloc[0]["Datetime"]

                resultXHtml = f"<div><span style='color:black'>x={date}</span>, <span style='color:black'>y={value}</span></div>"
                resultOHLCHtml = printOHLCInfo(currentBar)
                self.candlestickPlot.labelOHLC.setHtml(
                    resultXHtml + resultOHLCHtml
                )

            self.candlestickPlot.vLine.setPos(mousePoint.x())
            self.volumePlot.vLine.setPos(mousePoint.x())

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

            # udpate X axis of Volume
            self.volumePlot.setXRange(minVal, maxVal, padding=0)

            # udpate X axis of CANDLESTICK
            self.candlestickPlot.updateRange((minVal, maxVal))

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
