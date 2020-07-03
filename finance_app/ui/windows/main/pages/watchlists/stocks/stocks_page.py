import logging

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from ui.base.base_page import BasePage

from ui.windows.main.pages.watchlists.stocks.stocks_service import (
    StocksWatchlistService,
)
from ui.windows.main.pages.watchlists.stocks.table.table import StockTable
from ui.state.main import State

# create logger
log = logging.getLogger("CellarLogger")


class StocksWatchlistPage(BasePage):

    detailWindow = None

    tableSignal = pyqtSignal(dict)

    subscriptions = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log.info("Running ...")

        # self.bl = StocksWatchlistBL()
        self.state = State.getInstance()
        self.service = StocksWatchlistService()

        # load template
        uic.loadUi(
            "ui/windows/main/pages/watchlists/stocks/stocks_page.ui", self
        )

        # load styles
        with open(
            "ui/windows/main/pages/watchlists/stocks/stocks_page.qss", "r"
        ) as fh:
            self.setStyleSheet(fh.read())

        # Buttons
        self.startRealtime1Button.clicked.connect(self.addStockClick)
        self.loadSavedLayoutButton.clicked.connect(self.loadTableLayout)

        # tableView
        self.table = StockTable()
        self.table.on_remove.connect(self.removeStock)
        self.table.on_open.connect(self.openStock)
        self.table.on_order_changed.connect(self.updateWatchlist)
        self.tableBox1.addWidget(self.table)

        # SIGNALS
        self.tableSignal.connect(self.table.tableModel.on_update_model)

        self.loadTableLayout()

    def addStockClick(self):
        ticker = self.ticker1Input.text().upper()
        self.__startRealtime(ticker)

    # region "addStockClick" operators

    def __startRealtime(self, ticker):
        subscriptionTemp = self.service.startRealtimeAction(
            ticker
        ).ticks.subscribe(self.tableSignal.emit)

        self.subscriptions.append(subscriptionTemp)

    # endregion

    def removeStock(self, data):
        ticker = data.name

        self.table.tableModel.removeStock(ticker)
        self.service.remove(ticker)

    def openStock(self, data):
        # self.detailWindow = StocksDetailPage(data)
        # self.detailWindow.show()
        pass

    def updateWatchlist(self, data):
        self.service.updateStockWatchlist(data)

    def loadTableLayout(self):
        self.table.tableModel.reset()

        tickers = self.service.getWatchlist()
        for ticker in tickers["ticker"]:
            self.__startRealtime(ticker)

    # # --------------------------------------------------------
    # # --------------------------------------------------------
    # # DESTROY
    # # --------------------------------------------------------
    # # --------------------------------------------------------

    # # 1. CUSTOM destroy -----------------------------------------
    # def onDestroy(self):
    #     log.info("Destroying ...")

    #     # Unsubscribe everything
    #     for sub in self.subscriptions:
    #         sub.dispose()

    #     # destroy Service
    #     self.service.onDestroy()

    # # 2. Python destroy -----------------------------------------
    # def __del__(self):
    #     log.info("Running ...")
