import logging
from typing import Any, Tuple, Dict

import pandas as pd
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from rx import operators as ops
from rx.core.typing import Disposable

from ui.base.base_page import BasePage
from ui.windows.main.pages.watchlists.futures.futures_service import (
    FuturesWatchlistService,
)
from ui.windows.main.pages.watchlists.futures.table.tree import FuturesTree
from ui.windows.main.pages.watchlists.futures.table.tree_model import (
    FuturesTreeNode,
)
from ui.state.main import State

# create logger
log = logging.getLogger("CellarLogger")


class FuturesWatchlistPage(BasePage):

    detailWindow = None

    treeSignal = pyqtSignal(dict)

    subscriptions = []

    def __init__(self, *args: Tuple[str, Any], **kwargs: Dict[str, Any]):
        super().__init__(*args, **kwargs)
        log.info("Running ...")

        # self.bl = FuturesWatchlistBL()
        self.state = State.getInstance()
        self.service = FuturesWatchlistService()

        # load template
        uic.loadUi(
            "ui/windows/main/pages/watchlists/futures/futures_page.ui", self
        )

        # load styles
        with open(
            "ui/windows/main/pages/watchlists/futures/futures_page.qss", "r"
        ) as fh:
            self.setStyleSheet(fh.read())

        # Buttons
        self.startRealtime1Button.clicked.connect(self.addFutureClick)
        self.loadSavedLayoutButton.clicked.connect(self.loadTableLayout)

        # treeView
        self.tree = FuturesTree()
        self.tree.on_remove.connect(self.removeFuture)
        # self.table.on_open.connect(self.open)
        # self.table.on_order_changed.connect(self.update_watchlist)
        self.tableBox1.addWidget(self.tree)

        # SIGNALS
        self.treeSignal.connect(self.tree.tree_model.on_update_model)

        self.loadTableLayout()

    def addFutureClick(self):
        ticker: str = self.ticker1Input.text().upper()
        self.__startRealtime(ticker)

    # region "addFutureClick" operators

    def __startRealtime(self, ticker: str):

        subscriptionTemp: Disposable = (
            self.service.getNewestContractDetails(ticker)
            .pipe(
                ops.do_action(
                    # Update table based on data
                    self.tree.tree_model.addGroup
                ),
                ops.flat_map(self.service.startRealtimeForGroupAction),
            )
            .subscribe(self.treeSignal.emit)
        )

        self.subscriptions.append(subscriptionTemp)

    # endregion

    def removeFuture(self, node: FuturesTreeNode):
        symbol: str = node.data.index.values[0][0]
        localSymbol: str = node.data.index.values[0][1]

        self.tree.tree_model.removeFuture(symbol)
        self.service.remove(symbol, localSymbol)

    # def open(self, data):
    #     self.detailWindow = StocksDetailPage(data)
    #     self.detailWindow.show()

    # def updateWatchlist(self, data):
    #     self.bl.updateStockWatchlist(data)

    def loadTableLayout(self):
        self.tree.tree_model.reset()

        tickersDf: pd.DataFrame = self.service.getWatchlist()

        # ticker: str
        for ticker in tickersDf["ticker"]:  # type: str
            self.__startRealtime(ticker)

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

        # destroy Service
        self.service.onDestroy()

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
