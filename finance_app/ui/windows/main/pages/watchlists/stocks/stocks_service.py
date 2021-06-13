import logging
import random
import threading

import pandas as pd
from rx import Observable, of
from rx import operators as ops

from business.modules.stocks_watchlist_bl import StocksWatchlistBL
from business.model.contracts import (
    IBStockContract,
    IBContract,
)
from ui.state.main import State
from ui.state.stocks_realtime_data import StocksRealtimeDataItem

# create logger
log = logging.getLogger("CellarLogger")


class StocksWatchlistService(object):
    """ Service integrates BL and State management
    """

    def __init__(self):
        log.info("Running ...")

        # State
        self.state = State.getInstance()

        # BL
        self.bl = StocksWatchlistBL()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # ACTIONS (affecting state)
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def _route(self, data: dict, stateItem: StocksRealtimeDataItem):

        if data == {}:
            return

        if data["type"] == "ask":
            stateItem.ask.on_next(data)
        elif data["type"] == "ask_size":
            stateItem.askSize.on_next(data)
        elif data["type"] == "ask_exch":
            stateItem.askExch.on_next(data)
        elif data["type"] == "last":
            stateItem.last.on_next(data)
        elif data["type"] == "last_size":
            stateItem.lastSize.on_next(data)
        elif data["type"] == "last_exch":
            stateItem.lastExch.on_next(data)
        elif data["type"] == "last_timestamp":
            stateItem.lastTimestamp.on_next(data)
        elif data["type"] == "bid":
            stateItem.bid.on_next(data)
        elif data["type"] == "bid_size":
            stateItem.bidSize.on_next(data)
        elif data["type"] == "bid_exch":
            stateItem.bidExch.on_next(data)
        elif data["type"] == "open":
            stateItem.open.on_next(data)
        elif data["type"] == "high":
            stateItem.high.on_next(data)
        elif data["type"] == "low":
            stateItem.low.on_next(data)
        elif data["type"] == "close":
            stateItem.close.on_next(data)
        elif data["type"] == "volume":
            stateItem.volume.on_next(data)
        elif data["type"] == "option_historical_vol":
            stateItem.optionHistoricalVolatility.on_next(data)
        elif data["type"] == "option_implied_vol":
            stateItem.optionImpliedVolatility.on_next(data)
        elif data["type"] == "ib_dividends":
            stateItem.dividends.on_next(data)

    def startRealtimeAction(self, ticker) -> StocksRealtimeDataItem:
        print(ticker)

        stateItem = self.state.stocks_realtime_data.get(ticker, ticker)

        stateItem.ticks = self.bl.getContractDetails(ticker).pipe(
            ops.do_action(lambda x: log.info(x)),
            ops.flat_map(
                lambda x: self.bl.startRealtime(x.contract).pipe(
                    ops.filter(lambda x: x is not None),
                )
            ),
            ops.do_action(lambda x: self._route(x, stateItem)),
        )

        return stateItem

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def getWatchlist(self) -> pd.DataFrame:
        return self.bl.getWatchlist()

    def remove(self, ticker):
        self.bl.remove(ticker)

    def updateStockWatchlist(self, arr):
        self.bl.updateStockWatchlist(arr)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

        # destroy BL
        self.bl.onDestroy()

    # 2. Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
