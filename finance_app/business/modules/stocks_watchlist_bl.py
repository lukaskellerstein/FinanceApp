import logging
import threading
from typing import Any, List

import pandas as pd
from business.model.contracts import IBContract, IBStockContract
from business.model.factory.contract_detail_factory import (
    ContractDetailsFactory,
)
from business.model.factory.contract_factory import ContractFactory, SecType
from business.services.ibclient.my_ib_client import MyIBClient
from db.services.mongo_service import MongoService
from ibapi.contract import ContractDetails
from rx import Observable
from rx import operators as ops
from rx.core.typing import Observable

# create logger
log = logging.getLogger("CellarLogger")


class StocksWatchlistBL(object):
    """ Service integrates DB and IB
    """

    def __init__(self):
        log.info("Running ...")

        # connect to IB
        self.ibClient = MyIBClient()

        # start thread
        self.ibClient_thread = threading.Thread(
            name="StocksWatchlistBL-ibClient-thread",
            target=lambda: self.ibClient.myStart(),
            daemon=True,
        )
        self.ibClient_thread.start()

        # DB
        self.dbService = MongoService()

        # Business object factory
        self.contractFactory = ContractFactory()
        self.contractDetailsFactory = ContractDetailsFactory()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def getContractDetails(self, symbol: str) -> Observable[Any]:
        contract = self.contractFactory.createNewIBContract(
            SecType.STOCK, symbol, symbol
        )
        return self.ibClient.getContractDetail(contract).pipe(
            ops.filter(
                lambda contrDetails: isinstance(contrDetails, ContractDetails)
            ),
            ops.do_action(lambda x: log.info(x)),
            ops.do_action(lambda x: self.__addToDbContractDetails(x)),
        )

    # region "getContractDetails" operators

    def __addToDbContractDetails(self, x: ContractDetails):
        dictionary = self.contractDetailsFactory.createDict(x)
        self.dbService.addToStockContractDetails_IfNotExits(dictionary)

    # endregion

    # def getHistoricalData(self, ticker: str):
    #     contract = LlStock(ticker)
    #     return self.ibClient.getHistoricalData(contract)

    def getWatchlist(self) -> pd.DataFrame:
        return self.dbService.getStockWatchlist()

    def addToWatchlist(self, symbol: str):
        self.dbService.addToStockWatchlist_IfNotExists(symbol)

    def startRealtime(self, contract: IBContract) -> Observable[Any]:
        return self.ibClient.startRealtimeData(contract)

    def remove(self, ticker: str):
        # remove from watchlist DB
        self.dbService.removeFromStockWatchlist(ticker)

        # stop receiving data from Brokermg
        contract = self.contractFactory.createNewIBContract(
            SecType.STOCK, ticker, ticker
        )
        self.ibClient.stopRealtimeData(contract)

    def updateStockWatchlist(self, arr: List[str]):
        self.dbService.stocks_watchlist_table.drop()
        for item in arr:
            self.dbService.addToStockWatchlist(item)

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
