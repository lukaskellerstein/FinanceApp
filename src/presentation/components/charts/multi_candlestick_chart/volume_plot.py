import logging
import pyqtgraph as pg

from typing import Tuple

import pandas as pd
from PyQt6 import QtGui

# create logger
log = logging.getLogger("CellarLogger")


class VolumePlot(pg.PlotItem):
    def __init__(
        self, data: pd.DataFrame, currentRange: Tuple[int, int], **kwargs
    ):
        pg.PlotItem.__init__(self, **kwargs)

        self.setFixedHeight(100)

        # cross hair
        self.vLine = pg.InfiniteLine(
            angle=90, movable=False, pen=pg.mkPen(QtGui.QColor("black"))
        )
        self.addItem(self.vLine, ignoreBounds=True)

        # current range
        self.setXRange(*currentRange, padding=0)
        # (Afrom, Ato) = currentRange
        # self.painted: pd.DataFrame = self.data[
        #     (self.data["id"] >= Afrom) & (self.data["id"] <= Ato)
        # ].copy()

        # DRAW ALL CONTRACT MONTHS - VOLUME
        # Use iteration over groups instead of apply to avoid pandas deprecation warning
        for local_symbol, group_data in data.groupby("LocalSymbol"):
            self.drawContractMonthVolume(group_data)

    def drawContractMonthVolume(self, group_data):
        x = group_data["id"].to_list()
        y = group_data["Volume"].to_list()
        self.addItem(pg.BarGraphItem(x=x, height=y, width=0.5))
