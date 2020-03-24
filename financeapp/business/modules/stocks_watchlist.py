from ib_insync.contract import Stock

from ui.state.main import State
from business.core.task_manager import TaskManager
from business.services.ib_data_service import IBDataService
from db.services.mongo_service import MongoService


class StockWatchlistBL:
    def __init__(self):
        self.ibService = IBDataService()
        self.state = State.getInstance()
        self.taskManager = TaskManager.getInstance()
        self.dbService = MongoService()

    def remove(self, ticker):
        self.dbService.removeFromStockWatchlist(ticker)
        contract = self.state.stocks_watchlist.remove(ticker)
        self.ibService.stopRealtimeData(contract)
        self.state.stocks_realtime_data.remove(ticker)
        self.taskManager.close(ticker)

    def add(self, ticker, updateDB=True):
        contract = Stock(ticker, "SMART", "USD", primaryExchange="NASDAQ")
        result = self.ibService.getContractDetail(contract)
        if result is None:
            print(f"Contract {ticker} was not found")
        else:
            if updateDB:
                self.dbService.addToStockWatchlist(ticker)

            self.state.stocks_watchlist.add(ticker, contract)
            self.taskManager.run(
                ticker,
                self.ibService.startRealtimeData(
                    contract, self.state.stocks_realtime_data.update
                ),
            )

    def updateStateFromDB(self):
        tickers = self.dbService.getStockWatchlist()
        for ticker in tickers["ticker"]:
            self.add(ticker, False)
