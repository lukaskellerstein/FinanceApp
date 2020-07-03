import logging
from collections import defaultdict

from rx.subject import BehaviorSubject

# create logger
log = logging.getLogger("CellarLogger")


class FuturesRealtimeDataItem(object):
    def __init__(self, symbol, localSymbol):

        self.symbol = symbol
        self.localSymbol = localSymbol

        self.ticks = BehaviorSubject({})

        self.bid = BehaviorSubject(0.0)
        self.bidSize = BehaviorSubject(0)
        self.bidExch = BehaviorSubject(
            ""
        )  # Example: Z, KQ, NKTZ, BJQZ ...etc.

        self.last = BehaviorSubject(0.0)
        self.lastSize = BehaviorSubject(0)
        self.lastExch = BehaviorSubject(
            ""
        )  # Example: Z, KQ, NKTZ, BJQZ ...etc.
        self.lastTimestamp = BehaviorSubject(0)  # Example: 1587648950

        self.ask = BehaviorSubject(0.0)
        self.askSize = BehaviorSubject(0)
        self.askExch = BehaviorSubject(
            ""
        )  # Example: Z, KQ, NKTZ, BJQZ ...etc.

        self.open = BehaviorSubject(0.0)
        self.high = BehaviorSubject(0.0)
        self.low = BehaviorSubject(0.0)
        self.close = BehaviorSubject(0.0)

        self.volume = BehaviorSubject(0)

        self.optionHistoricalVolatility = BehaviorSubject(0.0)
        self.optionImpliedVolatility = BehaviorSubject(0.0)


class FuturesRealtimeDataState(object):
    def __init__(self):
        self.__data = defaultdict(None)

    def add(self, symbol: str, localSymbol: str) -> FuturesRealtimeDataItem:
        x = FuturesRealtimeDataItem(symbol, localSymbol)

        if (
            self.__data.get(self.__constructKey(symbol, localSymbol))
            is not None
        ):
            self.__data[self.__constructKey(symbol, localSymbol)] = x
        return x

    def get(self, symbol, localSymbol) -> FuturesRealtimeDataItem:
        x = self.__data.get(self.__constructKey(symbol, localSymbol))
        if x is None:
            return self.add(symbol, localSymbol)
        else:
            log.info(
                "Observable already exist in State ------------------------------------"
            )
            return x

    # ------------------------------------
    # HELEPRS
    # ------------------------------------
    def __constructKey(self, symbol: str, localSymbol: str) -> str:
        return f"{symbol}|{localSymbol}"
