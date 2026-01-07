from src.business.model.timeframe import TimeFrame
import logging
import threading
from datetime import datetime
from typing import Any, List, Tuple

import pandas as pd
from PyQt6 import uic
from PyQt6.QtCore import QModelIndex, Qt, pyqtSlot

from src.business.model.asset import Asset, AssetType
from src.business.modules.asset_bl import AssetBL
from src.ui.base.base_page import BasePage
from src.ui.components.search_input.search_input import SearchInput
from src.ui.windows.add_new_asset.add_asset_window import AssetAddWindow
from src.ui.windows.asset_detail.futures.future_detail_window import (
    FutureDetailWindow,
)
from src.ui.windows.asset_detail.shared.asset_detail_window import (
    AssetDetailWindow,
)
from src.ui.windows.asset_detail.stocks.stock_detail_window import (
    StockDetailWindow,
)
from src.ui.windows.main.pages.assets.table.table import AssetTable

# create logger
log = logging.getLogger("CellarLogger")


class AssetPage(BasePage):

    subscriptions = []
    lock = threading.Lock()

    tableData: List[Asset]

    timeframe: TimeFrame = TimeFrame.day1

    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("Running ...")
        self.setObjectName("asset_page")

        # load template
        uic.loadUi("src/ui/windows/main/pages/assets/asset_page.ui", self)

        # load styles
        with open("src/ui/windows/main/pages/assets/asset_page.qss", "r") as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.addWindow = None
        self.addButton.clicked.connect(self.openAddWindowHandler)
        self.updateAllButton.clicked.connect(self.updateAllHandler)

        self.assetType = kwargs["assetType"]
        self.bl = AssetBL()

        # tableView
        self.table = AssetTable()
        self.tableBox.addWidget(self.table)
        self.table.on_remove.connect(self.tableRemoveClickHandler)
        self.table.on_open.connect(self.tableOpenClickHandler)
        self.fillTable()

        # search widget
        self.searchWidget = SearchInput()
        self.searchWidgetBox.addWidget(self.searchWidget)
        self.searchWidget.on_textChanged.connect(self.searchEventHandler)

        # progress bar
        self.progressBar.hide()
        self.__updateProgress(0)

    def fillTable(self):
        self.tableData = self.bl.getAll(self.assetType)
        self.table.tableModel.setData(self.tableData)

    @pyqtSlot()
    def openAddWindowHandler(self):
        self.addWindow = AssetAddWindow(assetType=self.assetType)
        self.addWindow.on_close.connect(self.onCloseAddWindowHandler)
        self.addWindow.show()

    @pyqtSlot()
    def onCloseAddWindowHandler(self):
        self.addWindow.close()
        self.fillTable()

    @pyqtSlot()
    def updateAllHandler(self):

        self.progressBar.show()

        subscriptionTemp = self.bl.updateHistoricalData(
            self.tableData
        ).subscribe(self.__updateProgress)

        self.subscriptions.append(subscriptionTemp)

    @pyqtSlot(object)
    def __updateProgress(self, value):
        self.lock.acquire()
        progress = int(value)  # Convert float to int for QProgressBar
        print(f"Progress: {progress} %")
        try:
            self.progressBar.setValue(progress)

            if progress >= 100:
                self.progressBar.hide()
                self.fillTable()

        finally:
            self.lock.release()

    @pyqtSlot(object)
    def tableRemoveClickHandler(self, data: Tuple[pd.Series, QModelIndex]):
        (row, _) = data
        # remove from DB
        self.bl.remove(self.assetType, row["symbol"])

    @pyqtSlot(object)
    def tableOpenClickHandler(self, data: Tuple[pd.Series, QModelIndex]):
        (row, index) = data

        # log.info(index)
        # log.info(row)

        aa = list(filter(lambda x: x.symbol == row["symbol"], self.tableData))
        bb: Asset = aa[0]

        self.detailWindow = None
        if bb.type == AssetType.STOCK.value:
            self.detailWindow = StockDetailWindow(bb)
        elif bb.type == AssetType.FUTURE.value:
            self.detailWindow = FutureDetailWindow(bb)
        else:
            self.detailWindow = AssetDetailWindow(bb)

        self.detailWindow.on_update.connect(self.fillTable)
        self.detailWindow.show()

    @pyqtSlot(str)
    def searchEventHandler(self, text: str):
        self.table.tableModel.filterData(text)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

        # Unsubscribe everything
        for sub in self.subscriptions:
            sub.dispose()

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
