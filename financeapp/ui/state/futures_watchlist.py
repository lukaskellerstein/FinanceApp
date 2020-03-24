import pandas as pd

from rx import operators as ops
from rx.subject import BehaviorSubject


class FuturesItem:
    def __init__(self, ticker, contract):
        self.ticker = ticker
        self.contract = contract


class FuturesWatchlistState:

    __tickers = []
    tickers = BehaviorSubject(__tickers)

    def add(self, ticker, contract):
        item = FuturesItem(ticker, contract)
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
