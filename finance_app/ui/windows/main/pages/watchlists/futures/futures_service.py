import logging
from typing import Any, List

import pandas as pd

from rx import merge
from rx import operators as ops
from rx.core.typing import Observable

from business.modules.futures_watchlist_bl import FuturesWatchlistBL
from business.model.contracts import IBContract, IBFutureContract
from ibapi.contract import ContractDetails
from ui.state.main import State

# create logger
log = logging.getLogger("CellarLogger")


class FuturesWatchlistService(object):
    """ Service integrates BL and State management
    """

    def __init__(self):
        log.info("Running ...")

        # State
        self.state = State.getInstance()

        # BL
        self.bl = FuturesWatchlistBL()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # ACTIONS (affecting state)
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def startRealtimeForGroupAction(
        self, cds: List[ContractDetails]
    ) -> Observable[Any]:

        # save to DB
        self.bl.addToWatchlist(cds[0].contract)

        # create Observables
        resultList = []
        for cd in cds:
            contract = cd.contract

            ibContract = IBContract(**contract)

            stateItem = self.state.futures_realtime_data.get(
                contract.symbol, contract.localSymbol
            )

            stateItem.ticks = self.bl.startRealtime(ibContract).pipe(
                ops.filter(lambda x: x is not None),
            )

            stateItem.ask = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "ask")
            )
            stateItem.askSize = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "ask_size")
            )
            stateItem.askExch = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "ask_exch")
            )

            stateItem.last = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "last")
            )
            stateItem.lastSize = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "last_size")
            )
            stateItem.lastExch = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "last_exch")
            )
            stateItem.lastTimestamp = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "last_timestamp")
            )

            stateItem.bid = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "bid")
            )
            stateItem.bidSize = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "bid_size")
            )
            stateItem.bidExch = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "bid_exch")
            )

            stateItem.open = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "open")
            )
            stateItem.high = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "high")
            )
            stateItem.low = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "low")
            )
            stateItem.close = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "close")
            )

            stateItem.volume = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "volume")
            )

            stateItem.optionHistoricalVolatility = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "option_historical_vol")
            )
            stateItem.optionImpliedVolatility = stateItem.ticks.pipe(
                ops.filter(lambda x: x["type"] == "option_implied_vol")
            )

            resultList.append(stateItem.ticks)

        return merge(*resultList)

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def getNewestContractDetails(
        self, symbol: str
    ) -> Observable[List[ContractDetails]]:
        return self.bl.getNewestContractDetails(
            IBFutureContract(symbol=symbol), 3, 5
        )

    def getWatchlist(self) -> pd.DataFrame:
        return self.bl.getWatchlist()

    def remove(self, symbol: str, localSymbol: str):
        self.bl.remove(symbol, localSymbol)

    def updateStockWatchlist(self, arr: List[str]):
        self.bl.updateWatchlist(arr)

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
