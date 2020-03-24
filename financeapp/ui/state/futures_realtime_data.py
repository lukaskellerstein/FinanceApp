import pandas as pd

from rx import operators as ops
from rx.subject import BehaviorSubject

from helpers import printObject


class FuturesRealtimeDataState:
    # -------------------------------
    # -------------------------------
    # REWRITE TO DATAFRAME WITH multi-level index !!!!!!
    # -------------------------------
    # -------------------------------
    __data = pd.DataFrame(
        index=["ticker", "localSymbol"],
        columns=["bidSize", "bid", "ask", "askSize", "high", "low", "close"],
    )

    __data = {}

    data = BehaviorSubject(__data)

    # def remove(self, ticker):
    #     self.__data = self.__data.drop(ticker, axis=0)
    #     self.data.on_next(self.__data)

    def setData(self, symbol, innerSymbol):
        self.__data[symbol] = {}
        self.__data[symbol][innerSymbol] = pd.DataFrame(
            columns=["bidSize", "bid", "ask", "askSize", "high", "low", "close"]
        )

    def update(self, ticker):
        self.__data[ticker.contract.symbol][ticker.contract.localSymbol] = (
            ticker.bidSize,
            ticker.bid,
            ticker.ask,
            ticker.askSize,
            ticker.high,
            ticker.low,
            ticker.close,
        )

        self.data.on_next(self.__data)
