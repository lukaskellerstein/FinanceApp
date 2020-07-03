from helpers import week_of_month
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

import numpy as np
import pandas as pd
import pyqtgraph as pg
from dateutil.relativedelta import relativedelta
from holidays import US
from PyQt5 import uic
from PyQt5.QtCore import Qt, pyqtSlot
from trading_calendars import get_calendar

from business.model.asset import Asset, AssetType
from business.model.timeframe import TimeFrame, Duration
from business.modules.asset_bl import AssetBL
from ui.base.base_page import BasePage
from ui.components.candlestick_chart.chart import MyCandlestickChart
from PyQt5.QtGui import QColor


from typing import Tuple

# create logger
log = logging.getLogger("CellarLogger")


class HistoryChartPage(BasePage):
    asset: Asset
    bl: AssetBL

    originData: pd.DataFrame
    dataDF: pd.DataFrame

    currentRange: Tuple[int, int]

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("Running ...")

        # load template
        uic.loadUi(
            "ui/windows/asset_detail/shared/pages/history_chart/history_chart.ui",
            self,
        )

        # load styles
        with open(
            "ui/windows/asset_detail/shared/pages/history_chart/history_chart.qss",
            "r",
        ) as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WA_StyledBackground, True)

        # INPUT data
        self.asset: Asset = kwargs["asset"]

        # BL
        self.bl: AssetBL = AssetBL()

        # DEFAULTS
        self.currentRange = (0, 0)
        self.timeframe = TimeFrame.day1
        self.duration = Duration.year1.value

        # signals
        self.durationComboBox.currentTextChanged.connect(
            self.durationComboBoxChanged
        )
        self.usHolidaysCheckBox.stateChanged.connect(
            self.usHolidaysCheckboxChanged
        )
        self.weeksCheckbox.stateChanged.connect(self.weeksCheckboxChanged)
        self.monthsCheckbox.stateChanged.connect(self.monthsCheckboxChanged)
        self.seasonsCheckbox.stateChanged.connect(self.seasonsCheckboxChanged)
        self.quartersCheckbox.stateChanged.connect(
            self.quartersCheckboxChanged
        )
        self.yearsCheckbox.stateChanged.connect(self.yearsCheckboxChanged)

        # init chart ----------------------------------------------
        log.info("Running")
        start = time.time()
        self.__getHistData(self.timeframe)
        if self.data is not None:
            self.__fillGapsInDays(self.timeframe)
        end = time.time()
        log.info(f"enhance data takes: {end - start} sec.")

        if self.data is not None:
            start = time.time()
            self.originData = self.data.copy()
            self.__plotCandlestickChart(self.data, duration=self.duration)
            end = time.time()
            log.info(f"plotCandlestickChart data takes: {end - start} sec.")

            start = time.time()
            # self.__plotWeekends(self.data)
            end = time.time()
            log.info(f"plotWeekends data takes: {end - start} sec.")

        self.durationComboBox.setCurrentText(self.duration)
        # ---------------------------------------------------------

    def __getHistData(self, value: TimeFrame):
        start = time.time()
        self.data = self.bl.getHistoricalDataFromDB(self.asset.symbol, value)
        if self.data is not None:
            self.data = self.data.sort_index()

            # # check duplications
            # dupl = self.data.duplicated()
            # allresults = dupl[dupl == True]

        end = time.time()
        log.info(f"takes {end - start} sec.")

    def __fillGapsInDays(self, timeframe: TimeFrame):
        if timeframe.value == TimeFrame.day1.value:
            self.data = (
                self.data.asfreq("D").reset_index().set_index("Datetime")
            )

    def __plotCandlestickChart(self, data: pd.DataFrame, **kwargs: Any):

        # duration = self.getDuration()
        range = (0, 0)
        if "duration" in kwargs:
            range = self.getDuration(kwargs["duration"])
        elif "range" in kwargs:
            range = kwargs["range"]

        self.candlestickChart = MyCandlestickChart(data, range)

        self.candlestickChart.on_range_update.connect(self.__updateRange)
        self.chartBox.addWidget(self.candlestickChart, 0, 0, 0, 0)

    def __plotWeekends(self, data: pd.DataFrame):
        tempData = data.ffill(axis=0)
        tempData["id"] = np.arange(data.shape[0])

        # width
        w = (1 - 0) / 3.0
        ww = (1 - 0) / 2.0

        aaa = tempData[
            (tempData.index.weekday == 5) | (tempData.index.weekday == 6)
        ]

        aaa.apply(
            lambda x: self.__plotWeekendBar(
                x, self.candlestickChart.candlestickPlot, w, ww
            ),
            axis=1,
        )

    def __plotWeekendBar(self, row, plot, width1, width2):
        # BAR ----------------------------------
        bar = pg.QtGui.QGraphicsRectItem(
            row["id"] + width2 - width1,
            row["Low"],
            width1 * 2,
            row["High"] - row["Low"],
        )
        bar.setPen(pg.mkPen(None))
        bar.setBrush(pg.mkBrush(QColor("#bdbdbd")))
        plot.addItem(bar)

    # --------------------------------------------------------
    # COMBO-BOXES
    # --------------------------------------------------------

    @pyqtSlot(str)
    def durationComboBoxChanged(self, value: Duration):
        log.info("Running")
        start = time.time()

        self.duration = value

        if self.data is not None:
            range = self.getDuration(value)
            self.candlestickChart.overviewPlot.timeRegion.setRegion(range)

        end = time.time()
        log.info(f"durationComboBoxChanged data takes: {end - start} sec.")

    # --------------------------------------------------------
    # CHECK-BOXES
    # --------------------------------------------------------
    def __plotTimeRange(
        self,
        data: pd.DataFrame,
        method: Callable[[pd.Series, Any, float, float], Any],
        plot,
    ):
        data["id"] = np.arange(data.shape[0])

        minY = data["Low"].min()
        maxY = data["High"].max()

        data.apply(
            lambda x: method(x, plot, minY, maxY), axis=1,
        )

    def __plotTimeStatistics(
        self,
        rangeType: str,
        data: pd.DataFrame,
        method: Callable[[pd.Series, Any], Any],
        plot,
    ):

        data["Change"] = data["Close"].pct_change() * 100

        sum_change_data = data["Change"].resample(rangeType).sum()
        sum_change_data.name = "Sum"

        avg_change_data = data["Change"].resample(rangeType).mean()
        avg_change_data.name = "Avg"
        var_change_data = data["Change"].resample(rangeType).var()  # variance
        var_change_data.name = "Var"
        std_change_data = (
            data["Change"].resample(rangeType).std(ddof=2)
        )  # std dev
        std_change_data.name = "Std"

        id_data = data["id"].resample(rangeType).max()
        price_data = data["Close"].resample(rangeType).last()

        full_data = pd.concat(
            [
                id_data,
                price_data,
                sum_change_data,
                avg_change_data,
                var_change_data,
                std_change_data,
            ],
            axis=1,
        )

        full_data.apply(
            lambda x: method(x, plot), axis=1,
        )

    # HOLIDAYS ------------
    def __plotUSHolidays(self, data: pd.DataFrame):

        plot = self.candlestickChart.candlestickPlot

        holidayNames = US()
        nyse = get_calendar("XNYS")
        holidays = nyse.regular_holidays.holidays()

        # width
        w = (1 - 0) / 3.0
        ww = (1 - 0) / 2.0

        tempData = data.ffill(axis=0)
        tempData["id"] = np.arange(data.shape[0])

        tempDataMin = tempData.index.min()
        tempDataMax = tempData.index.max()

        for holiday in holidays:
            if tempDataMin < holiday < tempDataMax:
                # idx_holiday = tempData.index.get_loc(holiday.to_pydatetime())
                # val_holiday = tempData.loc[holiday.to_pydatetime()]["High"]

                row = tempData.loc[holiday.to_pydatetime()]

                # ARROW -----------------------------------
                arrow = pg.ArrowItem(
                    pos=(row["id"] + ww, row["High"]),
                    angle=-75,
                    tipAngle=60,
                    headLen=20,
                    tailLen=20,
                    tailWidth=10,
                    # pen={"color": "w", "width": 1},
                    brush=QColor("#8d8d8d"),
                )
                plot.addItem(arrow)

                # LABEL ---------------------------------
                label = pg.TextItem(
                    # html=f'<div style="text-align: center"><span style="color: #FFF;">{holidayNames.get(holiday)}</span></div>',
                    text=f"{holidayNames.get(holiday)}",
                    border="w",
                    # fill=(0, 0, 255, 100),
                    fill=QColor("#8d8d8d"),
                    anchor=(0.0, 2.5),
                )
                label.setPos(row["id"] + ww, row["High"])
                plot.addItem(label)

                # BAR ----------------------------------
                bar = pg.QtGui.QGraphicsRectItem(
                    row["id"] + ww - w,
                    row["Low"],
                    w * 2,
                    row["High"] - row["Low"],
                )

                bar.setPen(pg.mkPen(None))
                bar.setBrush(pg.mkBrush(QColor("gray")))
                plot.addItem(bar)

    @pyqtSlot(int)
    def usHolidaysCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotUSHolidays(self.data)
        else:
            self.__reDrawChart()

    # WEEKS ------------
    def __plotWeeks(self, data: pd.DataFrame):
        # COLOR BAR -------------------------
        # data["Week"] = data.apply(lambda x: week_of_month(x.name), axis=1)
        # self.__plotTimeRange(
        #     data, self.__plotWeekBar, self.candlestickChart.candlestickPlot
        # )

        plot = self.candlestickChart.candlestickPlot

        self.__plotTimeRange(data, self.__plotWeekBar, plot)

        # STATISTICS -------------------------
        self.__plotTimeStatistics(
            "W-MON",
            data,
            self.__plotStatistic,
            self.candlestickChart.candlestickPlot,
        )

    def __plotWeekBar(self, row: pd.Series, plot, minY: float, maxY: float):

        weekNum = row.name.isocalendar()[1]

        color = ""
        # if row.name.weekday() == 0:
        #     color = "#90caf9"
        # elif row.name.weekday() == 1:
        #     color = "#64b5f6"
        # elif row["Week"] == 2:
        #     color = "#42a5f5"
        # elif row["Week"] == 3:
        #     color = "#2196f3"
        # elif row["Week"] == 4:
        #     color = "#1e88e5"
        # elif row["Week"] == 5:
        #     color = "#1976d2"
        # elif row["Week"] == 6:
        #     color = "#000000"
        # else:
        #     log.info(row["Week"])
        #     color = "red"

        if (weekNum % 2) == 0:
            # odd number
            color = "#37474f"
        else:
            # even number
            color = "#b0bec5"

        # BAR ----------------------------------
        bar = pg.QtGui.QGraphicsRectItem(row["id"], minY, 1, maxY - minY)

        bar.setPen(pg.mkPen(None))
        bar.setOpacity(0.2)
        bar.setBrush(pg.mkBrush(QColor(color)))
        plot.addItem(bar)

    @pyqtSlot(int)
    def weeksCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotWeeks(self.data.copy())
        else:
            self.__reDrawChart()

    # MONTHS ------------
    def __plotMonths(self, data: pd.DataFrame):

        plot = self.candlestickChart.candlestickPlot

        # COLOR BAR -------------------------
        self.__plotTimeRange(data, self.__plotMonthBar, plot)

        # STATISTICS -------------------------
        self.__plotTimeStatistics(
            "M",
            data,
            self.__plotStatistic,
            self.candlestickChart.candlestickPlot,
        )

    def __plotMonthBar(self, row, plot, minY, maxY):
        color = ""

        # January - Q1 - Winter
        if row.name.month == 1:
            color = "#d32f2f"
        # February - Q1 - Winter
        elif row.name.month == 2:
            color = "#9c27b0"
        # March - Q1 - Spring
        elif row.name.month == 3:
            color = "#3f51b5"
        # April - Q2 - Spring
        elif row.name.month == 4:
            color = "#2196f3"
        # May - Q2 - Spring
        elif row.name.month == 5:
            color = "#00bcd4"
        # Jun - Q2 - Summer
        elif row.name.month == 6:
            color = "#009688"
        # July - Q3 - Summer
        elif row.name.month == 7:
            color = "#4caf50"
        # August - Q3 - Summer
        elif row.name.month == 8:
            color = "#cddc39"
        # September - Q3 - Autumn
        elif row.name.month == 9:
            color = "#ffeb3b"
        # October - Q4 - Autumn
        elif row.name.month == 10:
            color = "#ffc107"
        # November - Q4 - Autumn
        elif row.name.month == 11:
            color = "#ff9800"
        # December - Q4 - Winter
        elif row.name.month == 12:
            color = "#ff5722"
        else:
            log.info(row.name.month)
            color = "red"

        # BAR ----------------------------------
        bar = pg.QtGui.QGraphicsRectItem(row["id"], minY, 1, maxY - minY)

        bar.setPen(pg.mkPen(None))
        bar.setOpacity(0.2)
        bar.setBrush(pg.mkBrush(QColor(color)))
        plot.addItem(bar)

    @pyqtSlot(int)
    def monthsCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotMonths(self.data.copy())
        else:
            self.__reDrawChart()

    # SEASONS ------------
    def __plotSeasons(self, data: pd.DataFrame):
        plot = self.candlestickChart.candlestickPlot

        self.__plotTimeRange(data, self.__plotSeasonBar, plot)

    def __plotSeasonBar(self, row, plot, minY, maxY):
        color = ""

        # January - Q1 - Winter
        if row.name.month == 1:
            color = "#1e88e5"
        # February - Q1 - Winter
        elif row.name.month == 2:
            color = "#1e88e5"
        # March - Q1 - Spring
        elif row.name.month == 3:
            color = "#7cb342"
        # April - Q2 - Spring
        elif row.name.month == 4:
            color = "#7cb342"
        # May - Q2 - Spring
        elif row.name.month == 5:
            color = "#7cb342"
        # Jun - Q2 - Summer
        elif row.name.month == 6:
            color = "#e53935"
        # July - Q3 - Summer
        elif row.name.month == 7:
            color = "#e53935"
        # August - Q3 - Summer
        elif row.name.month == 8:
            color = "#e53935"
        # September - Q3 - Autumn
        elif row.name.month == 9:
            color = "#4e342e"
        # October - Q4 - Autumn
        elif row.name.month == 10:
            color = "#4e342e"
        # November - Q4 - Autumn
        elif row.name.month == 11:
            color = "#4e342e"
        # December - Q4 - Winter
        elif row.name.month == 12:
            color = "#1e88e5"
        else:
            color = "red"
            print("????????????????????????")

        # BAR ----------------------------------
        bar = pg.QtGui.QGraphicsRectItem(row["id"], minY, 1, maxY - minY)

        bar.setPen(pg.mkPen(None))
        bar.setOpacity(0.2)
        bar.setBrush(pg.mkBrush(QColor(color)))
        plot.addItem(bar)

    @pyqtSlot(int)
    def seasonsCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotSeasons(self.data.copy())
        else:
            self.__reDrawChart()

    # QUARTERS ------------
    def __plotQuarters(self, data: pd.DataFrame):

        plot = self.candlestickChart.candlestickPlot

        # COLOR BAR -------------------------
        self.__plotTimeRange(data, self.__plotQuarterBar, plot)

        # STATISTICS -------------------------
        self.__plotTimeStatistics(
            "Q",
            data,
            self.__plotStatistic,
            self.candlestickChart.candlestickPlot,
        )

    def __plotQuarterBar(self, row, plot, minY, maxY):
        color = ""

        # January - Q1 - Winter
        if row.name.month == 1:
            color = "#b0bec5"
        # February - Q1 - Winter
        elif row.name.month == 2:
            color = "#b0bec5"
        # March - Q1 - Spring
        elif row.name.month == 3:
            color = "#b0bec5"
        # April - Q2 - Spring
        elif row.name.month == 4:
            color = "#78909c"
        # May - Q2 - Spring
        elif row.name.month == 5:
            color = "#78909c"
        # Jun - Q2 - Summer
        elif row.name.month == 6:
            color = "#78909c"
        # July - Q3 - Summer
        elif row.name.month == 7:
            color = "#546e7a"
        # August - Q3 - Summer
        elif row.name.month == 8:
            color = "#546e7a"
        # September - Q3 - Autumn
        elif row.name.month == 9:
            color = "#546e7a"
        # October - Q4 - Autumn
        elif row.name.month == 10:
            color = "#37474f"
        # November - Q4 - Autumn
        elif row.name.month == 11:
            color = "#37474f"
        # December - Q4 - Winter
        elif row.name.month == 12:
            color = "#37474f"
        else:
            print("????????????????????????")

        # BAR ----------------------------------
        bar = pg.QtGui.QGraphicsRectItem(row["id"], minY, 1, maxY - minY)

        bar.setPen(pg.mkPen(None))
        bar.setOpacity(0.2)
        bar.setBrush(pg.mkBrush(QColor(color)))
        plot.addItem(bar)

    @pyqtSlot(int)
    def quartersCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotQuarters(self.data.copy())
        else:
            self.__reDrawChart()

    # YEARS ------------
    def __plotYears(self, data: pd.DataFrame):

        plot = self.candlestickChart.candlestickPlot

        # COLOR BAR -------------------------
        self.__plotTimeRange(data, self.__plotYearBar, plot)

        # STATISTICS -------------------------
        self.__plotTimeStatistics(
            "Y",
            data,
            self.__plotStatistic,
            self.candlestickChart.candlestickPlot,
        )

    def __plotYearBar(self, row, plot, minY, maxY):
        color = ""

        if (row.name.year % 2) == 0:
            # odd number
            color = "#37474f"
        else:
            # even number
            color = "#b0bec5"

        bar = pg.QtGui.QGraphicsRectItem(row["id"], minY, 1, maxY - minY)

        bar.setPen(pg.mkPen(None))
        bar.setOpacity(0.2)
        bar.setBrush(pg.mkBrush(QColor(color)))
        plot.addItem(bar)

    def __plotStatistic(self, row, plot):

        # ARROW -----------------------------------
        arrow = pg.ArrowItem(
            pos=(row["id"], row["Close"]),
            angle=0,
            tipAngle=60,
            headLen=20,
            tailLen=20,
            tailWidth=10,
            # pen={"color": "w", "width": 1},
            brush=QColor("#303f9f"),
        )
        plot.addItem(arrow)

        # LABELS ----------------------------------
        label = pg.TextItem(
            html=f"""
            <div style="text-align: center">
                <span style="color: #FFF;">Return: {round(row["Sum"])} %</span>
            </div>
            <div style="text-align: center">
                <span style="color: #FFF;">Daily Return: {round(row["Avg"],2)} %</span>
            </div>
            <div style="text-align: center">
                <span style="color: #FFF;">Variance: {round(row["Var"],2)}</span>
            </div>
            <div style="text-align: center">
                <span style="color: #FFF;">StdDev: {round(row["Std"],2)}</span>
            </div>
            """,
            # text=f"{round(row['Change'])} %",
            # border="w",
            # fill=(0, 0, 255, 100),
            fill=QColor("#303f9f"),
            anchor=(0.0, 0.0),
        )
        label.setPos(row["id"], row["Close"])
        plot.addItem(label)

    @pyqtSlot(int)
    def yearsCheckboxChanged(self, state: int):
        if state == Qt.Checked:
            self.__plotYears(self.data.copy())
        else:
            self.__reDrawChart()

    # --------------------------------------------------------
    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    # --------------------------------------------------------

    def __reDrawChart(self):
        self.__plotCandlestickChart(self.originData, range=self.currentRange)
        self.__plotWeekends(self.originData)

        if self.usHolidaysCheckBox.isChecked():
            self.__plotUSHolidays(self.originData)

        if self.weeksCheckbox.isChecked():
            self.__plotWeeks(self.originData)

        if self.monthsCheckbox.isChecked():
            self.__plotMonths(self.originData)

        if self.seasonsCheckbox.isChecked():
            self.__plotSeasons(self.originData)

        if self.quartersCheckbox.isChecked():
            self.__plotQuarters(self.originData)

        if self.yearsCheckbox.isChecked():
            self.__plotYears(self.originData)

    def __updateRange(self, range: Tuple[int, int]):
        self.currentRange = range

    def getDuration(self, duration: Duration):
        minVal = datetime.now()
        maxVal = datetime.now()
        if duration == Duration.years20.value:
            minVal = maxVal - relativedelta(years=20)
        elif duration == Duration.years10.value:
            minVal = maxVal - relativedelta(years=10)
        elif duration == Duration.year5.value:
            minVal = maxVal - relativedelta(years=5)
        elif duration == Duration.year1.value:
            minVal = maxVal - relativedelta(years=1)
        elif duration == Duration.quarter1.value:
            minVal = maxVal - relativedelta(months=3)
        elif duration == Duration.month1.value:
            minVal = maxVal - relativedelta(months=1)
        elif duration == Duration.week1.value:
            minVal = maxVal - relativedelta(weeks=1)
        elif duration == Duration.all.value:
            minVal = datetime.min

        minIndex = 0
        maxIndex = self.data.shape[0]

        if minVal != datetime.min:
            tempDf = self.data[self.data.index > minVal]
            if tempDf.shape[0] > 0:
                minIndex = self.data.index.get_loc(tempDf.index[0])

        return (minIndex, maxIndex)

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
