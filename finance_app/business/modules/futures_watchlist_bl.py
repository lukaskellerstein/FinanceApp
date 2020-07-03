import logging
import threading
from datetime import date, datetime
from typing import Any, List, Union

import pandas as pd

from rx import operators as ops
from rx.core.typing import Observable

from business.model.contracts import (
    IBContract,
    IBFutureContract,
)
from business.services.ibclient.my_ib_client import MyIBClient
from db.services.mongo_service import MongoService
from helpers import mapContractDetailsToLl, obj_to_dict
from ibapi.contract import Contract, ContractDetails

# create logger
log = logging.getLogger("CellarLogger")


allowExchanges = ["GLOBEX", "ECBOT", "NYMEX", "NYBOT"]


class FuturesWatchlistBL(object):
    def __init__(self):
        log.info("Running ...")

        # connect to IB
        self.ibClient = MyIBClient()

        # start thread
        self.ibClient_thread = threading.Thread(
            name="FuturesWatchlistBL-ibClient-thread",
            target=lambda: self.ibClient.myStart(),
            daemon=True,
        )
        self.ibClient_thread.start()

        # DB
        self.dbService = MongoService()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def getNewestContractDetails(
        self,
        contract: IBContract,
        count: int,
        bufferTime: int
        # ) -> Subject[ContractDetails, ContractDetails]:
    ) -> Observable[List[ContractDetails]]:

        return self.ibClient.getContractDetail(contract).pipe(
            ops.filter(
                lambda contrDetails: isinstance(contrDetails, ContractDetails)
            ),
            ops.filter(self.__filterExchange),
            ops.filter(self.__filterOlderThanToday),
            ops.do_action(self.__addToDbContractDetails),
            ops.buffer_with_time(bufferTime),
            ops.filter(self.__filterEmptyArray),
            ops.map(lambda x: self.__chooseContractMonths(x, count)),
            # ops.map(self.__selectContract),
        )

    # region "getFirstContractDetails" operators

    def __filterEmptyArray(self, arr: List[Any]) -> bool:
        return True if len(arr) > 0 else False

    def __addToDbContractDetails(self, x: ContractDetails):

        aaa = mapContractDetailsToLl(x)
        bbb = obj_to_dict(aaa)

        self.dbService.addToFuturesContractDetails_IfNotExits(bbb)

        return aaa

    def __filterOlderThanToday(self, cd: ContractDetails) -> bool:
        lastDate = datetime.strptime(
            cd.contract.lastTradeDateOrContractMonth, "%Y%m%d"
        ).date()
        nowDate = date.today()
        if lastDate < nowDate:
            return False
        else:
            return True

    def __filterExchange(self, cd: ContractDetails) -> bool:
        if cd.contract.exchange in allowExchanges:
            return True
        else:
            return False

    def __chooseContractMonths(
        self, data: List[ContractDetails], count: int
    ) -> List[ContractDetails]:
        data.sort(key=lambda x: x.contract.lastTradeDateOrContractMonth)
        return data[:count]

    # def __selectContract(
    #     self, data: List[ContractDetails]
    # ) -> List[MyContract]:
    #     return map(lambda x: x.contract, data)

    # endregion

    # def getHistoricalData(self, ticker):
    #     contract = LlFuture(ticker)
    #     return self.ibClient.getHistoricalData(contract)

    def getWatchlist(self) -> pd.DataFrame:
        return self.dbService.getFuturesWatchlist()

    def addToWatchlist(self, contract: Union[IBContract, Contract]):
        self.dbService.addToFuturesWatchlist_IfNotExists(contract.symbol)

    def startRealtime(self, contract: IBContract) -> Observable[Any]:
        return self.ibClient.startRealtimeData(contract)

    def remove(self, symbol: str, localSymbol: str):
        # remove from watchlist DB
        self.dbService.removeFromFuturesWatchlist(symbol)

        # stop receiving data from Broker
        contract = IBFutureContract(symbol=symbol, localSymbol=localSymbol)
        self.ibClient.stopRealtimeData(contract)

    def updateWatchlist(self, arr: List[Any]):
        self.dbService.futures_watchlist_table.drop()
        for item in arr:
            self.dbService.addToFuturesWatchlist(item)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. - CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

        # Close DB
        self.dbService.client.close()
        self.dbService.db.logout()

        # Close IB
        self.ibClient.connectionClosed()  # close the EWrapper
        self.ibClient.disconnect()  # close the EClient

    # 2. - Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
