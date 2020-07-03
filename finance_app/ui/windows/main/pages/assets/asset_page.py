import logging
from typing import Any, List, Tuple

import pandas as pd
from PyQt5 import uic
from PyQt5.QtCore import QModelIndex, Qt, pyqtSlot

from business.model.asset import Asset, AssetType
from business.modules.asset_bl import AssetBL
from ui.base.base_page import BasePage
from ui.components.search_input.search_input import SearchInput
from ui.windows.add_new_asset.add_asset_window import AssetAddWindow
from ui.windows.asset_detail.shared.asset_detail_window import (
    AssetDetailWindow,
)
from ui.windows.main.pages.assets.table.table import AssetTable
from ui.windows.asset_detail.stocks.stock_detail_window import (
    StockDetailWindow,
)
from ui.windows.asset_detail.futures.future_detail_window import (
    FutureDetailWindow,
)

# create logger
log = logging.getLogger("CellarLogger")


class AssetPage(BasePage):
    def __init__(self, **kwargs: Any):
        super().__init__()
        log.info("Running ...")

        # load template
        uic.loadUi("ui/windows/main/pages/assets/asset_page.ui", self)

        # load styles
        with open("ui/windows/main/pages/assets/asset_page.qss", "r") as fh:
            self.setStyleSheet(fh.read())

        # apply styles
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.addWindow = None
        self.addButton.clicked.connect(self.openAddWindowHandler)

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

    def fillTable(self):
        self.tableData: List[Asset] = self.bl.getAllFromDb(self.assetType)
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

    @pyqtSlot(object)
    def tableRemoveClickHandler(self, data: Tuple[pd.Series, QModelIndex]):
        (row, _) = data
        # remove from DB
        self.bl.removeFromDb(self.assetType, row["symbol"])

    @pyqtSlot(object)
    def tableOpenClickHandler(self, data: Tuple[pd.Series, QModelIndex]):
        (row, index) = data

        log.info(index)
        print(row)

        aa = list(filter(lambda x: x.symbol == row["symbol"], self.tableData))
        bb: Asset = aa[0]

        if bb.type == AssetType.STOCK.value:
            self.detailWindow = StockDetailWindow(bb)
            self.detailWindow.show()
        elif bb.type == AssetType.FUTURE.value:
            self.detailWindow = FutureDetailWindow(bb)
            self.detailWindow.show()
        else:
            self.detailWindow = AssetDetailWindow(bb)
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

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
