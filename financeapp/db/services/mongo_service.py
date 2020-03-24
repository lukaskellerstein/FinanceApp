import pymongo
import pandas as pd


class MongoService:
    def __init__(self):
        self.client = pymongo.MongoClient("mongodb://localhost:27017/")
        self.db = self.client["cellarstone-app"]
        self.stock_watchlist_table = self.db["stock-watchlist"]
        self.futures_watchlist_table = self.db["futures-watchlist"]

    def getStockWatchlist(self):
        return pd.DataFrame(self.stock_watchlist_table.find())

    def addToStockWatchlist(self, ticker):
        self.stock_watchlist_table.insert_one({"ticker": ticker})

    def removeFromStockWatchlist(self, ticker):
        self.stock_watchlist_table.delete_one({"ticker": ticker})

    def getFuturesWatchlist(self):
        return pd.DataFrame(self.futures_watchlist_table.find())

    def addToFuturesWatchlist(self, ticker):
        self.futures_watchlist_table.insert_one({"ticker": ticker})

    def removeFromFuturesWatchlist(self, ticker):
        self.futures_watchlist_table.delete_one({"ticker": ticker})
