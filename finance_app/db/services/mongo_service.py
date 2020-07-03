import logging
from typing import Any, List, Dict

import pandas as pd
import pymongo


# create logger
log = logging.getLogger("CellarLogger")


class MongoService:
    def __init__(self):
        self.client: pymongo.MongoClient = pymongo.MongoClient(
            "mongodb://localhost:27017/"
        )
        self.db: Any = self.client["cellarstone-app"]
        self.stocks_watchlist_table = self.db["stock-watchlist"]
        self.stocks_contract_details_table = self.db["stock-contract-details"]
        self.futures_watchlist_table = self.db["futures-watchlist"]
        self.futures_contract_details_table = self.db[
            "futures-contract-details"
        ]

    # -----------------------------------------------------------------
    # Dynamic
    # -----------------------------------------------------------------
    def find(
        self, tableName: str, findObject: Dict[str, str] = {}
    ) -> List[Any]:
        return self.db[tableName].find(findObject)

    def findOne(self, tableName: str, findObject: Dict[str, str] = {}) -> Any:
        return self.db[tableName].find_one(findObject)

    def add(self, tableName: str, obj: Dict[str, str] = {}):
        self.db[tableName].insert_one(obj)

    # -----------------------------------------------------------------
    # Stocks
    # -----------------------------------------------------------------

    # Watchlist ----------------------------------------------

    def addToStockWatchlist_IfNotExists(self, ticker: str):
        asset = self.stocks_watchlist_table.find({"ticker": ticker})
        if asset.count() == 0:
            self.addToStockWatchlist(ticker)

    def getStockWatchlist(self) -> pd.DataFrame:
        return pd.DataFrame(self.stocks_watchlist_table.find())

    def addToStockWatchlist(self, ticker: str):
        self.stocks_watchlist_table.insert_one({"ticker": ticker})

    def removeFromStockWatchlist(self, ticker: str):
        self.stocks_watchlist_table.delete_one({"ticker": ticker})

    # Contract details---------------------------------------

    def addToStockContractDetails_IfNotExits(
        self, contract_details: Dict[str, str]
    ):
        asset: pd.DataFrame = self.getStockContractDetailsAsPanda(
            contract_details["symbol"], contract_details["localSymbol"]
        )

        # print("----------------------")
        # print(asset)
        # print(asset.size)
        # print(contract_details)
        # print("----------------------")
        if asset.size == 0:
            self.addToStockContractDetails(contract_details)

    def getStockContractDetailsAsPanda(
        self, symbol: str, localSymbol: str
    ) -> pd.DataFrame:
        return pd.DataFrame(
            self.stocks_contract_details_table.find(
                {"symbol": symbol, "localSymbol": localSymbol}
            )
        )

    def getStockContractDetail(
        self, symbol: str, localSymbol: str
    ) -> Dict[str, str]:
        return self.stocks_contract_details_table.find_one(
            {"symbol": symbol, "localSymbol": localSymbol}
        )

    def addToStockContractDetails(self, contract_details: Dict[str, str]):
        self.stocks_contract_details_table.insert_one(contract_details)

    def removeFromStockContractDetails(self, contract_details: Dict[str, str]):
        self.stocks_contract_details_table.delete_one(contract_details)

    # -----------------------------------------------------------------
    # Futures
    # -----------------------------------------------------------------

    # Watchlist ----------------------------------------------

    def addToFuturesWatchlist_IfNotExists(self, ticker: str):
        asset = self.futures_watchlist_table.find({"ticker": ticker})
        # print("----------------------")
        # print(asset.count())
        # print("----------------------")
        if asset.count() == 0:
            self.addToFuturesWatchlist(ticker)

    def getFuturesWatchlist(self) -> pd.DataFrame:
        return pd.DataFrame(self.futures_watchlist_table.find())

    def addToFuturesWatchlist(self, ticker: str):
        self.futures_watchlist_table.insert_one({"ticker": ticker})

    def removeFromFuturesWatchlist(self, ticker: str):
        self.futures_watchlist_table.delete_one({"ticker": ticker})

    # Contract details---------------------------------------

    def addToFuturesContractDetails_IfNotExits(
        self, contract_details: Dict[str, str]
    ):
        asset: pd.DataFrame = self.getFuturesContractDetails(
            contract_details["symbol"], contract_details["localSymbol"]
        )
        # print("----------------------")
        # print(asset)
        # print(asset.size)
        # print("----------------------")
        if asset.size == 0:
            self.addToFuturesContractDetails(contract_details)

    def getFuturesContractDetails(
        self, symbol: str, local_symbol: str
    ) -> pd.DataFrame:
        return pd.DataFrame(
            self.futures_contract_details_table.find(
                {"symbol": symbol, "localSymbol": local_symbol}
            )
        )

    def addToFuturesContractDetails(self, contract_details: Dict[str, str]):
        self.futures_contract_details_table.insert_one(contract_details)

    def removeFromFuturesContractDetails(
        self, contract_details: Dict[str, str]
    ):
        self.futures_contract_details_table.delete_one(contract_details)

    # Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
