from __future__ import (
    annotations,
)  # allow return same type as class ..... -> IBContract

from ibapi.contract import Contract
from db.model.base import DBObject


class ContractFactory(object):
    @staticmethod
    def create(contractType: str, **kwargs: str) -> IBContract:
        if contractType == "stock":
            return IBStockContract(**kwargs)
        elif contractType == "future":
            return IBFutureContract(**kwargs)
        else:
            return IBContract(**kwargs)


class IBContract(Contract, DBObject):
    def __init__(self, **kwargs: str):
        Contract.__init__(self)
        DBObject.__init__(self, self.__module__, type(self).__name__)

        # dynamically set attributes
        for (k, v) in kwargs.items():
            setattr(self, k, v)

    def key(self):
        return f"{self.symbol}|{self.localSymbol}"


class IBStockContract(IBContract):
    def __init__(self, **kwargs: str):
        super().__init__(**kwargs)

        self.secType = "STK"
        self.exchange = "SMART"
        self.currency = "USD"
        self.primaryExchange = "NASDAQ"


class IBFutureContract(IBContract):
    def __init__(self, **kwargs: str):
        super().__init__(**kwargs)
        self.secType = "FUT"
        self.includeExpired = True


# class IBContFutureContract(IBContract):
#     def __init__(self, **kwargs: str):
#         super().__init__(**kwargs)
#         self.secType = "CONTFUT"
#         self.exchange = "GLOBEX"


class IBOptionContract(IBContract):
    def __init__(self, **kwargs: str):
        super().__init__(**kwargs)
        self.secType = "OPT"
        self.currency = "USD"
