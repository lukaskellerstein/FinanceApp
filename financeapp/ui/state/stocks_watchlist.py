import pandas as pd

from rx import operators as ops
from rx.subject import BehaviorSubject


class StockItem:
    def __init__(self, ticker, contract):
        self.ticker = ticker
        self.contract = contract


class StocksWatchlistState:

    __tickers = []
    tickers = BehaviorSubject(__tickers)

    def add(self, ticker, contract):
        item = StockItem(ticker, contract)
        self.__tickers.append(item)
        self.tickers.on_next(self.__tickers)

    def remove(self, ticker):
        items = filter(lambda x: x.ticker == ticker, self.__tickers)
        result = None
        for item in items:
            if item is not None:
                result = item
                self.__tickers.remove(item)
                self.tickers.on_next(self.__tickers)

        return result.contract

