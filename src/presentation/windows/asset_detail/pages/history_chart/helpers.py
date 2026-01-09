"""
Chart overlay helpers for the history chart page.

Adapted from the old src/ui/windows/asset_detail/shared/pages/history_chart/helpers.py
to work with the new Clean Architecture.
"""

import pandas as pd
import pyqtgraph as pg
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsRectItem
import numpy as np
from typing import Callable, Any

from holidays import US
from exchange_calendars import get_calendar

from src.domain.entities.timeframe import TimeFrame


def fillGapsInDays(data: pd.DataFrame, timeframe: TimeFrame) -> pd.DataFrame:
    """Fill gaps in daily data."""
    if timeframe == TimeFrame.DAY_1:
        data = data.asfreq("D").reset_index().set_index("Datetime")
    return data


def _get_rectangle_object(
    color: str, opacity: float, x: int, y: float, width: float, height: float
) -> QGraphicsRectItem:
    """Create a colored rectangle for chart overlay."""
    bar = QGraphicsRectItem(x, y, width, height)
    bar.setPen(pg.mkPen(None))
    bar.setOpacity(opacity)
    bar.setBrush(pg.mkBrush(QColor(color)))
    return bar


def _plot_time_range(
    data: pd.DataFrame,
    method: Callable[[pd.Series, Any, float, float], Any],
    plot: pg.PlotItem,
) -> None:
    """Plot time range overlay."""
    minY = data["Low"].min()
    maxY = data["High"].max()
    data.apply(lambda x: method(x, plot, minY, maxY), axis=1)


def _plot_time_statistics(
    rangeType: str,
    data: pd.DataFrame,
    method: Callable[[pd.Series, Any], Any],
    plot: pg.PlotItem,
) -> None:
    """Plot time-based statistics."""
    data["Change"] = data["Close"].pct_change() * 100

    sum_change_data = data["Change"].resample(rangeType).sum()
    sum_change_data.name = "Sum"

    avg_change_data = data["Change"].resample(rangeType).mean()
    avg_change_data.name = "Avg"
    var_change_data = data["Change"].resample(rangeType).var()
    var_change_data.name = "Var"
    std_change_data = data["Change"].resample(rangeType).std(ddof=2)
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

    full_data.apply(lambda x: method(x, plot), axis=1)


def _plot_statistic(row: pd.Series, plot: pg.PlotItem) -> None:
    """Plot statistics arrow and label."""
    # Arrow
    arrow = pg.ArrowItem(
        pos=(row["id"], row["Close"]),
        angle=0,
        tipAngle=60,
        headLen=20,
        tailLen=20,
        tailWidth=10,
        brush=QColor("#303f9f"),
    )
    plot.addItem(arrow)

    # Labels
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
        fill=QColor("#303f9f"),
        anchor=(0.0, 0.0),
    )
    label.setPos(row["id"], row["Close"])
    plot.addItem(label)


# HOLIDAYS --------------------------------------------------------

def plotUSHolidays(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot US holidays on the chart."""
    holidayNames = US()
    nyse = get_calendar("XNYS")
    holidays = nyse.regular_holidays.holidays()

    w = (1 - 0) / 3.0
    ww = (1 - 0) / 2.0

    tempData = data.ffill(axis=0)
    tempData["id"] = np.arange(data.shape[0])

    tempDataMin = tempData.index.min()
    tempDataMax = tempData.index.max()

    for holiday in holidays:
        if tempDataMin < holiday < tempDataMax:
            try:
                row = tempData.loc[holiday.to_pydatetime()]

                # Arrow
                arrow = pg.ArrowItem(
                    pos=(row["id"] + ww, row["High"]),
                    angle=-75,
                    tipAngle=60,
                    headLen=20,
                    tailLen=20,
                    tailWidth=10,
                    brush=QColor("#8d8d8d"),
                )
                plot.addItem(arrow)

                # Label
                label = pg.TextItem(
                    text=f"{holidayNames.get(holiday)}",
                    border="w",
                    fill=QColor("#8d8d8d"),
                    anchor=(0.0, 2.5),
                )
                label.setPos(row["id"] + ww, row["High"])
                plot.addItem(label)

                # Bar
                bar = QGraphicsRectItem(
                    row["id"] + ww - w,
                    row["Low"],
                    w * 2,
                    row["High"] - row["Low"],
                )
                bar.setPen(pg.mkPen(None))
                bar.setBrush(pg.mkBrush(QColor("gray")))
                plot.addItem(bar)
            except (KeyError, IndexError):
                continue


# WEEKS --------------------------------------------------------

def plotWeeks(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot week overlays on the chart."""
    _plot_time_range(data, _plot_week_bar, plot)
    _plot_time_statistics("W-MON", data, _plot_statistic, plot)


def _plot_week_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single week bar."""
    weekNum = row.name.isocalendar()[1]

    if (weekNum % 2) == 0:
        color = "#37474f"
    else:
        color = "#b0bec5"

    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


# WEEKENDS --------------------------------------------------------

def plotWeekends(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot weekends on the chart."""
    tempData = data.ffill(axis=0)
    tempData["id"] = np.arange(data.shape[0])

    w = (1 - 0) / 3.0
    ww = (1 - 0) / 2.0

    weekendData = tempData[
        (tempData.index.weekday == 5) | (tempData.index.weekday == 6)
    ]

    weekendData.apply(
        lambda x: _plot_weekend_bar(x, plot, w, ww), axis=1,
    )


def _plot_weekend_bar(
    row: pd.DataFrame, plot: pg.PlotItem, width1: float, width2: float
) -> None:
    """Plot a single weekend bar."""
    color = "#bdbdbd"
    bar = _get_rectangle_object(
        color,
        1,
        row["id"] + width2 - width1,
        row["Low"],
        width1 * 2,
        row["High"] - row["Low"],
    )
    plot.addItem(bar)


# MONTHS --------------------------------------------------------

def plotMonths(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot month overlays on the chart."""
    _plot_time_range(data, _plot_month_bar, plot)
    _plot_time_statistics("M", data, _plot_statistic, plot)


def _plot_month_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single month bar with unique color per month."""
    month_colors = {
        1: "#d32f2f",   # January - Winter
        2: "#9c27b0",   # February - Winter
        3: "#3f51b5",   # March - Spring
        4: "#2196f3",   # April - Spring
        5: "#00bcd4",   # May - Spring
        6: "#009688",   # June - Summer
        7: "#4caf50",   # July - Summer
        8: "#cddc39",   # August - Summer
        9: "#ffeb3b",   # September - Autumn
        10: "#ffc107",  # October - Autumn
        11: "#ff9800",  # November - Autumn
        12: "#ff5722",  # December - Winter
    }
    color = month_colors.get(row.name.month, "red")
    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


# SEASONS --------------------------------------------------------

def plotSeasons(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot season overlays on the chart."""
    _plot_time_range(data, _plot_season_bar, plot)


def _plot_season_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single season bar."""
    month = row.name.month
    if month in [12, 1, 2]:  # Winter
        color = "#1e88e5"
    elif month in [3, 4, 5]:  # Spring
        color = "#7cb342"
    elif month in [6, 7, 8]:  # Summer
        color = "#e53935"
    else:  # Autumn (9, 10, 11)
        color = "#4e342e"

    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


# QUARTERS --------------------------------------------------------

def plotQuarters(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot quarter overlays on the chart."""
    _plot_time_range(data, _plot_quarter_bar, plot)
    _plot_time_statistics("Q", data, _plot_statistic, plot)


def _plot_quarter_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single quarter bar."""
    month = row.name.month
    if month in [1, 2, 3]:  # Q1
        color = "#b0bec5"
    elif month in [4, 5, 6]:  # Q2
        color = "#78909c"
    elif month in [7, 8, 9]:  # Q3
        color = "#546e7a"
    else:  # Q4 (10, 11, 12)
        color = "#37474f"

    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


# YEARS --------------------------------------------------------

def plotYears(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot year overlays on the chart."""
    _plot_time_range(data, _plot_year_bar, plot)
    _plot_time_statistics("Y", data, _plot_statistic, plot)


def _plot_year_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single year bar."""
    if (row.name.year % 2) == 0:
        color = "#37474f"
    else:
        color = "#b0bec5"

    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


# DECADES --------------------------------------------------------

def plotDecades(data: pd.DataFrame, plot: pg.PlotItem) -> None:
    """Plot decade overlays on the chart."""
    _plot_time_range(data, _plot_decade_bar, plot)
    _plot_time_statistics("10YE", data, _plot_statistic, plot)


def _plot_decade_bar(row: pd.Series, plot: pg.PlotItem, minY: float, maxY: float) -> None:
    """Plot a single decade bar."""
    decade = row.name.year // 10
    if (decade % 2) == 0:
        color = "#1a237e"  # Dark indigo
    else:
        color = "#7986cb"  # Light indigo

    bar = _get_rectangle_object(color, 0.2, row["id"], minY, 1, maxY - minY)
    plot.addItem(bar)


def hasDecadeOfData(data: pd.DataFrame) -> bool:
    """Check if data spans at least 10 years."""
    if data is None or data.empty:
        return False
    date_range = data.index.max() - data.index.min()
    return date_range.days >= 365 * 10
