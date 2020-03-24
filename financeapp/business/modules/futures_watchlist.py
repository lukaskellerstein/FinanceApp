from ib_insync.contract import Stock, Future, Contract

from ui.state.main import State
from business.core.task_manager import TaskManager
from business.services.ib_data_service import IBDataService
from db.services.mongo_service import MongoService

import pandas as pd


class FuturesWatchlistBL:
    def __init__(self):
        self.ibService = IBDataService()
        self.state = State.getInstance()
        self.taskManager = TaskManager.getInstance()
        self.dbService = MongoService()

    def remove(self, ticker):
        self.dbService.removeFromFuturesWatchlist(ticker)
        contract = self.state.futures_watchlist.remove(ticker)
        self.ibService.stopRealtimeData(contract)
        self.state.futures_realtime_data.remove(ticker)
        self.taskManager.close(ticker)

    def add(self, ticker, updateDB=True):

        contract = Contract()
        contract.symbol = ticker
        contract.secType = "FUT"
        contract.exchange = "NYMEX"

        allContracts = self.ibService.getFuturesContractDetail(contract)

        if allContracts is None:
            print(f"Contract {ticker} was not found")
        else:
            self.state.futures_watchlist.add(ticker, contract)
            aaa = list(
                map(lambda x: x.contract.lastTradeDateOrContractMonth, allContracts)
            )
            aaa.sort(key=int)

            bbb = aaa[:5]
            print(bbb)

            ccc = list(
                filter(
                    lambda x: x.contract.lastTradeDateOrContractMonth in bbb,
                    allContracts,
                )
            )

            for item in ccc:

                innerContract = Future(
                    symbol=item.contract.symbol,
                    localSymbol=item.contract.localSymbol,
                    exchange="NYMEX",
                )

                self.state.futures_realtime_data.setData(
                    item.contract.symbol, item.contract.localSymbol
                )

                self.taskManager.run(
                    item.contract.localSymbol,
                    self.ibService.startRealtimeData(
                        innerContract, self.state.futures_realtime_data.update
                    ),
                )
        pass

    def updateStateFromDB(self):
        # tickers = self.dbService.getStockWatchlist()
        # for ticker in tickers["ticker"]:
        #     self.add(ticker, False)
        pass
