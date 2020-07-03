import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List

from rx import operators as ops
from rx.core.typing import Observable
from rx.subject.behaviorsubject import BehaviorSubject

from business.helpers import getTimeBlocks
from business.model.asset import Asset, AssetType
from business.model.contract_details import IBContractDetails
from business.model.contracts import IBContract
from business.model.timeframe import TimeFrame
from business.services.ibclient.my_ib_client import MyIBClient
from business.tasks.download_hist_data_task import DownloadHistDataTask
from db.services.mongo_asset_service import MongoAssetService
from db.services.pystore_hist_service import PyStoreHistService

# create logger
log = logging.getLogger("CellarLogger")


class AssetBL(object):
    """ Service integrates DB and IB
    """

    def __init__(self):
        log.info("Running ...")

        # connect to IB
        self.ibClient = MyIBClient()

        # start thread
        self.ibClient_thread = threading.Thread(
            name=f"AssetBL-ibClient-{self.ibClient.uid}-thread",
            target=lambda: self.ibClient.myStart(),
            daemon=True,
        )
        self.ibClient_thread.start()

        self.currentThread = None

        # DB
        self.assetDbService = MongoAssetService()
        self.histDataDbService = PyStoreHistService()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    # CONTRACT DETAILS - IB ---------------------------
    def getContractDetails(
        self, assetType: AssetType, contract: IBContract
    ) -> Observable[IBContractDetails]:
        if assetType == AssetType.FUTURE:
            return self.ibClient.getContractDetail(contract).pipe(
                ops.filter(lambda x: x is not None),
                ops.buffer_with_time(2),
                ops.take(1),
            )
        elif assetType == AssetType.STOCK:
            return self.ibClient.getContractDetail(contract).pipe(
                ops.filter(lambda x: x is not None),
                ops.buffer_with_time(1),
                ops.take(1),
            )

    # ASSET - DB ---------------------------
    def existInDb(self, assetType: AssetType, symbol: str) -> bool:
        isExist = self.assetDbService.findOne(assetType, {"symbol": symbol})
        return True if isExist is not None else False

    def saveToDb(self, asset: Asset):
        self.assetDbService.add(AssetType.from_str(asset.type), asset)

    def getAllFromDb(self, assetType: AssetType) -> List[Asset]:
        return self.assetDbService.getAll(assetType)

    def removeFromDb(self, assetType: AssetType, symbol: str):
        self.assetDbService.remove(assetType, {"symbol": symbol})

    # REALTIME DATA - IB ---------------------------
    def startRealtime(self, contract: IBContract) -> Observable[Any]:
        return self.ibClient.startRealtimeData(contract)

    # HISTORICAL DATA - IB + DB ---------------------------
    def downloadHistoricalData(
        self,
        contractsAndTimeBlocks: List[Dict],
        blockSize: int = 7,  # in days
        timeframe: TimeFrame = TimeFrame.day1,
    ) -> Observable[Any]:
        progressResult0000 = BehaviorSubject(0)

        self.currentThread = DownloadHistDataTask(
            self.ibClient,
            progressResult0000,
            contractsAndTimeBlocks,
            timeframe,
            blockSize,
        )
        self.currentThread.start()

        return progressResult0000

    def getHistoricalDataFromDB(self, symbol: str, timeframe: TimeFrame):
        return self.histDataDbService.getAll(symbol, timeframe)

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. - CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

        if self.currentThread is not None:
            self.currentThread.terminate()

        # Close DB
        self.assetDbService.client.close()
        self.assetDbService.db.logout()

        # Close IB
        self.ibClient.connectionClosed()  # close the EWrapper
        self.ibClient.disconnect()  # close the EClient

    # 2. - Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
