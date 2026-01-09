"""
Demonstrate creation of a custom graphic (a candlestick plot)
"""
import logging
import time

import numpy as np
import pandas as pd
import pyqtgraph as pg
from pyqtgraph import QtCore, QtGui
from PyQt6.QtGui import QColor
from datetime import datetime, timedelta

from typing import Tuple, List, Any, Dict

# create logger
log = logging.getLogger("CellarLogger")


class CandlestickPlot(pg.PlotItem):
    def __init__(
        self, data: pd.DataFrame, currentRange: Tuple[int, int], **kwargs
    ):
        pg.PlotItem.__init__(self, **kwargs)

        self.plots: Dict[str, Any] = {}
        # Store expiration lines and their positions for highlighting
        self.expiration_lines: Dict[str, pg.InfiniteLine] = {}
        self.expiration_positions: Dict[str, int] = {}  # groupName -> x position
        self.expiration_original_colors: Dict[str, QColor] = {}  # Store original line colors
        self.expiration_original_label_opts: Dict[str, dict] = {}  # Store original label options
        self.highlighted_expiration: str = ""  # Currently highlighted expiration line
        self.data = data.reset_index().copy()

        # help data
        self.dataDate = self.data.copy()
        self.dataDate = self.dataDate.set_index(["Datetime"])

        self.dataInt = self.data.copy()
        self.dataInt = self.dataInt.set_index(["id"])

        # grid
        self.showGrid(x=True)

        # cross hair
        self.vLine = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(QtGui.QColor("black"))
        )
        self.hLine = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen(QtGui.QColor("black"))
        )
        self.addItem(self.vLine, ignoreBounds=True)
        self.addItem(self.hLine, ignoreBounds=True)

        # labels
        self.labelOHLC = pg.TextItem(text="")
        self.addItem(self.labelOHLC)
        self.labelOHLC.setPos(0, 0)

        # current range
        self.setXRange(*currentRange, padding=0)
        (Afrom, Ato) = currentRange
        self.painted: pd.DataFrame = self.data[
            (self.data["id"] >= Afrom) & (self.data["id"] <= Ato)
        ].copy()

        # DRAW ALL
        self.drawAll(self.painted)

    def updateRange(self, currentRange: Tuple[int, int]):

        (Afrom, Ato) = currentRange

        if Afrom < 0:
            Afrom = 0
        elif Afrom > self.data["id"].max():
            Afrom = self.data["id"].max()

        if Ato < 0:
            Ato = 0
        elif Ato > self.data["id"].max():
            Ato = self.data["id"].max()

        log.info(f"update Range: {Afrom}, {Ato}")

        if Afrom != Ato:

            # current range
            tempDf = self.data[
                (self.data["id"] >= Afrom) & (self.data["id"] <= Ato)
            ].copy()

            # difference with painted DF
            self.bbb = tempDf.drop(self.painted.index, axis=0, errors="ignore")

            if self.bbb.shape[0] > 0:

                # enhanced painted dataDF
                self.painted = pd.concat([self.painted, self.bbb], ignore_index=False)
                self.painted = self.painted.sort_values("index")

                # DRAW ALL
                self.drawAll(self.painted)

            self.setXRange(*currentRange, padding=0)
            self.setYRange(
                tempDf["Low"].min(), tempDf["High"].max(), padding=0,
            )

            self.labelOHLC.setPos(Afrom, tempDf["High"].max())

    def drawAll(self, data):

        self.clear()
        # Clear expiration tracking when redrawing
        self.expiration_lines.clear()
        self.expiration_positions.clear()
        self.expiration_original_colors.clear()
        self.expiration_original_label_opts.clear()
        self.highlighted_expiration = ""

        # DRAW ALL CONTRACT MONTHS - CANDLESTICK and EXPIRATIONS
        # Use iteration over groups instead of apply to avoid pandas deprecation warning
        # and to ensure grouping columns are available
        for (local_symbol, last_trade_date), group_data in data.groupby(["LocalSymbol", "LastTradeDate"]):
            self.drawContractMonthCandlestick(group_data, local_symbol, last_trade_date)
            self.drawContractMonthExpiration(group_data, local_symbol, last_trade_date)

    def drawContractMonthCandlestick(self, data, local_symbol: str, last_trade_date: str):
        graphics = CandlestickGraphics(data)
        self.plots[f"{local_symbol}-{last_trade_date}"] = graphics
        self.addItem(graphics)

    def drawContractMonthExpiration(self, data, local_symbol: str, last_trade_date: str):
        from datetime import timezone

        # Parse the date and make it timezone-aware to match the data
        lastDatetime = datetime.strptime(last_trade_date, "%Y%m%d").replace(tzinfo=timezone.utc)

        lastId = data.tail(1)["id"].iloc[0] + 1

        lastLocalSymbol = local_symbol
        groupName = f"{local_symbol}-{last_trade_date}"

        if lastDatetime in self.dataDate.index:
            vLineTemp = pg.InfiniteLine(
                angle=90,
                movable=False,
                label=f"{lastDatetime.strftime('%Y%m%d')}-{lastLocalSymbol}",
                labelOpts={
                    "position": 0.1,
                    "color": QColor("#ffeb3b"),
                    "fill": QColor("#fbc02d"),
                    "movable": True,
                },
            )
            vLineTemp.setPos(lastId)
            self.addItem(vLineTemp)
            # Store line reference, position, original color and label options
            self.expiration_lines[groupName] = vLineTemp
            self.expiration_positions[groupName] = lastId
            self.expiration_original_colors[groupName] = QColor("#ffeb3b")  # Yellow
            self.expiration_original_label_opts[groupName] = {
                "color": QColor("#ffeb3b"),
                "fill": QColor("#fbc02d"),
            }
        else:
            lastId = self.dataDate.tail(1)["id"].iloc[0]
            lastDT = self.dataDate.tail(1).index[0]

            # Ensure lastDT is timezone-aware for comparison
            if hasattr(lastDT, 'tz') and lastDT.tz is None:
                lastDT = lastDT.replace(tzinfo=timezone.utc)
            elif isinstance(lastDT, datetime) and lastDT.tzinfo is None:
                lastDT = lastDT.replace(tzinfo=timezone.utc)

            res = (lastDatetime - lastDT).days
            linePos = lastId + res

            vLineTemp = pg.InfiniteLine(
                angle=90,
                movable=False,
                pen=QColor("#3949ab"),
                label=f"{lastDatetime.strftime('%Y%m%d')}-{lastLocalSymbol}",
                labelOpts={
                    "position": 0.9,
                    "color": QColor("#3949ab"),
                    "fill": QColor("#9fa8da"),
                    "movable": True,
                },
            )
            vLineTemp.setPos(linePos)
            self.addItem(vLineTemp)
            # Store line reference, position, original color and label options
            self.expiration_lines[groupName] = vLineTemp
            self.expiration_positions[groupName] = linePos
            self.expiration_original_colors[groupName] = QColor("#3949ab")  # Violet
            self.expiration_original_label_opts[groupName] = {
                "color": QColor("#3949ab"),
                "fill": QColor("#9fa8da"),
            }

    def setGroupOpacity(self, groupName: str, opacity: float):
        if groupName in self.plots:
            self.plots[groupName].setOpacity(opacity)

    def setExpirationHighlight(self, groupName: str, highlight: bool):
        """Highlight or unhighlight an expiration line by making it green and thicker."""
        green_color = QColor("#00c853")  # Bright green
        green_fill = QColor("#69f0ae")   # Light green fill

        # Unhighlight the previously highlighted line - restore original colors
        if self.highlighted_expiration and self.highlighted_expiration in self.expiration_lines:
            old_line = self.expiration_lines[self.highlighted_expiration]
            original_color = self.expiration_original_colors.get(
                self.highlighted_expiration, QColor("#3949ab")
            )
            original_label_opts = self.expiration_original_label_opts.get(
                self.highlighted_expiration, {"color": QColor("#3949ab"), "fill": QColor("#9fa8da")}
            )
            # Restore line pen
            old_line.setPen(pg.mkPen(original_color, width=1))
            # Restore label colors
            if old_line.label is not None:
                old_line.label.setColor(original_label_opts["color"])
                old_line.label.fill = pg.mkBrush(original_label_opts["fill"])
                old_line.label.update()

        # Highlight the new line - make it GREEN and thicker
        if highlight and groupName in self.expiration_lines:
            line = self.expiration_lines[groupName]
            # Set line to green and thick
            line.setPen(pg.mkPen(green_color, width=4))
            # Set label to green
            if line.label is not None:
                line.label.setColor(green_color)
                line.label.fill = pg.mkBrush(green_fill)
                line.label.update()
            self.highlighted_expiration = groupName
        else:
            self.highlighted_expiration = ""


## Create a subclass of GraphicsObject.
## The only required methods are paint() and boundingRect()
## (see QGraphicsItem documentation)
class CandlestickGraphics(pg.GraphicsObject):

    lastDate: str = ""

    def __init__(self, data):
        pg.GraphicsObject.__init__(self)
        self.picture = QtGui.QPicture()
        self.painter = None
        self.w = 1 / 3.0
        self.ww = 1 / 2.0
        self.generatePicture(data)

    def generatePicture(self, data: pd.DataFrame):
        start = time.time()
        if data.shape[0] > 0:
            ## pre-computing a QPicture object allows paint() to run much more quickly,
            ## rather than re-drawing the shapes every time.

            if self.painter is None:
                self.painter = QtGui.QPainter(self.picture)

            p = self.painter

            p.begin(self.picture)
            p.setPen(pg.mkPen(QtGui.QColor("black")))

            data.apply(
                lambda x: self.rowDoSomething(p, x, self.w, self.ww), axis=1
            )

            p.end()
            self.update()

        end = time.time()
        log.info(f"generatePicture takes: {end - start} sec.")

    def rowDoSomething(self, p, row, width1, width2):
        xAxis = row["id"] + width2
        if pd.isna(row["Open"]) == False:
            p.drawLine(
                QtCore.QPointF(xAxis, row["Low"]),
                QtCore.QPointF(xAxis, row["High"]),
            )
            if row["Open"] > row["Close"]:
                p.setBrush(pg.mkBrush(QtGui.QColor("red")))
            else:
                p.setBrush(pg.mkBrush(QtGui.QColor("green")))

            p.drawRect(
                QtCore.QRectF(
                    xAxis - width1,
                    row["Open"],
                    width1 * 2,
                    row["Close"] - row["Open"],
                )
            )

    def paint(self, p, *args):
        p.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        ## boundingRect _must_ indicate the entire area that will be drawn on
        ## or else we will get artifacts and possibly crashing.
        ## (in this case, QPicture does all the work of computing the bouning rect for us)
        return QtCore.QRectF(self.picture.boundingRect())
