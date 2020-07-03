import logging
from collections import defaultdict
from typing import Any, DefaultDict

import pandas as pd
from rx import operators as ops
from rx.subject import BehaviorSubject

# create logger
log = logging.getLogger("CellarLogger")


class StocksRealtimeDataItem(object):
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

        self.dividends = BehaviorSubject(
            ""
        )  # Example: 3.0284,3.1628,20200723,0.7907


class StocksRealtimeDataState(object):
    __data: DefaultDict[str, Any]

    def __init__(self):
        self.__data = defaultdict(None)

    def add(self, symbol, localSymbol) -> StocksRealtimeDataItem:
        x = StocksRealtimeDataItem(symbol, localSymbol)
        self.__data[self.__constructKey(symbol, localSymbol)] = x
        return x

    def get(self, symbol, localSymbol) -> StocksRealtimeDataItem:
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
    def __constructKey(self, symbol, localSymbol) -> str:
        return f"{symbol}|{localSymbol}"
