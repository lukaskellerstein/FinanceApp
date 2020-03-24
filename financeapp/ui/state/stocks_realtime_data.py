import pandas as pd

from rx import operators as ops
from rx.subject import BehaviorSubject


class StocksRealtimeDataState:

    __data = pd.DataFrame(
        columns=["bidSize", "bid", "ask", "askSize", "high", "low", "close"],
    )

    data = BehaviorSubject(__data)

    def remove(self, ticker):
        aaa = self.__data.drop(ticker, axis=0)
        print(aaa)
        self.__data = aaa
        self.data.on_next(self.__data)

    def update(self, ticker):

        self.__data.loc[ticker.contract.symbol] = (
            ticker.bidSize,
            ticker.bid,
            ticker.ask,
            ticker.askSize,
            ticker.high,
            ticker.low,
            ticker.close,
        )

        self.data.on_next(self.__data)
