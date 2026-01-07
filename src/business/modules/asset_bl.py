from src.business.model.factory.asset_factory import AssetFactory
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from rx import operators as ops
from rx.core.typing import Observable
from rx.subject.behaviorsubject import BehaviorSubject

from src.business.helpers import getTimeBlocks
from src.business.model.asset import Asset, AssetType
from src.business.model.contract_details import IBContractDetails
from src.business.model.contracts import IBContract
from src.business.model.timeframe import TimeFrame
from src.business.services.ibclient.my_ib_client import MyIBClient
from src.business.tasks.download_hist_data_task import DownloadHistDataTask
from src.db.services.json_asset_service import JsonAssetService
from src.db.services.pystore_hist_service import PyStoreHistService
from src.business.model.factory.contract_factory import ContractFactory
from src.business.model.factory.contract_detail_factory import (
    ContractDetailsFactory,
)

# create logger
log = logging.getLogger("CellarLogger")


class AssetBL(object):
    """ Service integrates DB and IB
    """

    def __init__(self):
        log.info("Running ...")

        # connect to IB
        self.__ibClient = MyIBClient()

        # start thread
        self.__ibClient_thread = threading.Thread(
            name=f"AssetBL-ibClient-{self.__ibClient.uid}-thread",
            target=lambda: self.__ibClient.myStart(),
            daemon=True,
        )
        self.__ibClient_thread.start()

        self.__currentThread = None

        # DB
        self.__assetDbService = JsonAssetService()
        self.__histDataDbService = PyStoreHistService()

        # Business object factory
        self.__assetFactory = AssetFactory()
        self.__contractFactory = ContractFactory()
        self.__contractDetailsFactory = ContractDetailsFactory()

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # BUSINESS LOGIC
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    # ASSET - DB ---------------------------
    def get(self, assetType: AssetType, symbol: str) -> Union[None, Asset]:
        resultDict = self.__assetDbService.findOne(
            assetType, {"symbol": symbol}
        )

        if resultDict == None:
            log.warn(f"Asset with symbol: {symbol} is not found in Asset DB")
            return None

        result = self.__assetFactory.createAsset(resultDict)
        return result

    def isExist(self, assetType: AssetType, symbol: str) -> bool:
        isExist = self.__assetDbService.findOne(assetType, {"symbol": symbol})
        return True if isExist is not None else False

    def save(self, asset: Asset):
        dbobject = self.__assetFactory.createDict(asset)
        self.__assetDbService.add(AssetType.from_str(asset.type), dbobject)

    def getAll(self, assetType: AssetType) -> List[Asset]:
        dbobjects = self.__assetDbService.getAll(assetType)
        objects: List[Asset] = [
            self.__assetFactory.createAsset(dbobject) for dbobject in dbobjects
        ]
        return objects

    def remove(self, assetType: AssetType, symbol: str):
        self.__assetDbService.remove(assetType, {"symbol": symbol})

    # CONTRACT DETAILS - IB ---------------------------
    def getContractDetails(
        self, assetType: AssetType, contract: IBContract
    ) -> Observable[IBContractDetails]:
        log.info(contract)
        if assetType == AssetType.FUTURE:
            return self.__ibClient.getContractDetail(contract).pipe(
                ops.filter(lambda x: x is not None),
                ops.buffer_with_time(2),
                ops.take(1),
            )
        elif assetType == AssetType.STOCK:
            return self.__ibClient.getContractDetail(contract).pipe(
                ops.filter(lambda x: x is not None),
                ops.buffer_with_time(1),
                ops.take(1),
            )

    def getLatestContractDetails(
        self, assetType: AssetType, symbol: str, latestContractDetails: int = 1
    ) -> List[IBContractDetails]:
        # Asset
        asset = self.get(assetType, symbol)
        if asset is None:
            log.warn(f"Asset with symbol: {symbol} is not found in Asset DB")
            return []

        # Choose the right contract
        contractDetails = asset.latestContractDetails(latestContractDetails)
        return contractDetails if contractDetails is not None else []

    # REALTIME DATA - IB ---------------------------
    def startRealtime(self, contract: IBContract) -> Observable[Any]:
        return self.__ibClient.startRealtimeData(contract).pipe(
            ops.filter(lambda x: x is not None),
        )

    def stopRealtime(self, contract: IBContract) -> None:
        return self.__ibClient.stopRealtimeData(contract)

    # HISTORICAL DATA - IB + DB ---------------------------
    def downloadHistoricalData(
        self,
        assets: List[Asset],
        timeframe: TimeFrame = TimeFrame.day1,
        maxBlockSize: int = 365,  # in days
    ) -> Observable[Any]:
        progressResult0000 = BehaviorSubject(0)

        contractsAndTimeBlocks = []

        for asset in assets:
            # Clear existing data first - Download means fresh download
            try:
                if AssetType.from_str(asset.type) == AssetType.STOCK:
                    log.info(f"Clearing existing data for {asset.symbol} before download")
                    self.__histDataDbService.removeAll(asset.symbol, timeframe)
                elif AssetType.from_str(asset.type) == AssetType.FUTURE:
                    # For futures, clear all contract data
                    for cd in asset.contractDetails:
                        localSymbol = f"{cd.contract.localSymbol}-{cd.contract.lastTradeDateOrContractMonth}"
                        log.info(f"Clearing existing data for {localSymbol} before download")
                        self.__histDataDbService.removeAll(localSymbol, timeframe)
            except Exception as e:
                log.warning(f"Error clearing data for {asset.symbol}: {e}")

            if AssetType.from_str(asset.type) == AssetType.STOCK:
                contractsAndTimeBlocks.extend(
                    self.__downloadStock(asset, maxBlockSize)
                )
            elif AssetType.from_str(asset.type) == AssetType.FUTURE:
                contractsAndTimeBlocks.extend(
                    self.__downloadFutures(asset, maxBlockSize)
                )

        self.__currentThread = DownloadHistDataTask(
            self.__ibClient,
            progressResult0000,
            contractsAndTimeBlocks,
            timeframe,
        )
        self.__currentThread.start()

        return progressResult0000

    def updateHistoricalData(
        self,
        assets: List[Asset],
        timeframe: TimeFrame = TimeFrame.day1,
        maxBlockSize: int = 365,  # in days
    ) -> Observable[Any]:
        progressResult0000 = BehaviorSubject(0)

        contractsAndTimeBlocks = []

        for asset in assets:
            if AssetType.from_str(asset.type) == AssetType.STOCK:
                contractsAndTimeBlocks.extend(
                    self.__updateStock(asset, timeframe, maxBlockSize)
                )

            elif AssetType.from_str(asset.type) == AssetType.FUTURE:
                contractsAndTimeBlocks.extend(
                    self.__updateFutures(asset, timeframe, maxBlockSize)
                )

        log.info(contractsAndTimeBlocks)

        self.__currentThread = DownloadHistDataTask(
            self.__ibClient,
            progressResult0000,
            contractsAndTimeBlocks,
            timeframe,
        )
        self.__currentThread.start()

        return progressResult0000

    def getHistoricalDataFromDB(self, symbol: str, timeframe: TimeFrame):
        return self.__histDataDbService.getAll(symbol, timeframe)

    # FUNDAMENTALS DATA - IB -----------------------------------
    def getFundamentals(self, contract: IBContract) -> Observable[Any]:
        return self.__ibClient.getFundamentalData(contract)

    # ----------------------------------------------------------
    # ----------------------------------------------------------
    # HELPER METHODS
    # ----------------------------------------------------------
    # ----------------------------------------------------------

    def __checkForSplits(
        self, contract: IBContract, symbol: str, sinceDate: datetime, timeframe: TimeFrame
    ) -> bool:
        """
        Check if any stock splits occurred since the given date.
        If splits detected, clears the historical data for re-download.
        Returns True if splits were detected and data was cleared.
        """
        log.info(f"Checking for splits for {symbol} since {sinceDate}")

        splits_result = []
        check_complete = threading.Event()

        def on_splits(splits: List[Dict]):
            nonlocal splits_result
            splits_result = splits
            check_complete.set()

        def on_error(e):
            log.warning(f"Error getting split history for {symbol}: {e}")
            check_complete.set()

        def on_complete():
            check_complete.set()

        try:
            subscription = self.__ibClient.getSplitHistory(contract).subscribe(
                on_next=on_splits,
                on_error=on_error,
                on_completed=on_complete,
            )

            # Wait for split check to complete (max 10 seconds)
            check_complete.wait(timeout=10)
            subscription.dispose()

        except Exception as e:
            log.warning(f"Exception checking splits for {symbol}: {e}")
            return False

        if not splits_result:
            log.info(f"No split history found for {symbol}")
            return False

        # Check if any split occurred after sinceDate
        # Make sinceDate timezone-aware if it isn't
        if sinceDate.tzinfo is None:
            sinceDate = sinceDate.replace(tzinfo=timezone.utc)

        splits_since = [
            s for s in splits_result
            if s["date"].replace(tzinfo=timezone.utc) > sinceDate
        ]

        if splits_since:
            log.warning(
                f"SPLIT DETECTED for {symbol}! "
                f"Found {len(splits_since)} split(s) since {sinceDate}: "
                f"{[(s['date'], s['ratio']) for s in splits_since]}"
            )
            log.info(f"Clearing historical data for {symbol} to re-download with adjusted prices")

            # Clear the existing data
            try:
                self.__histDataDbService.removeAll(symbol, timeframe)
                log.info(f"Successfully cleared data for {symbol}")
            except Exception as e:
                log.error(f"Error clearing data for {symbol}: {e}")

            return True

        log.info(f"No splits detected for {symbol} since {sinceDate}")
        return False

    def __updateFutures(
        self, asset: Asset, timeframe: TimeFrame, maxBlockSize: int
    ) -> List[Dict]:
        result = []

        for cd in asset.contractDetails:

            lastTradeDateTime = datetime.strptime(
                cd.contract.lastTradeDateOrContractMonth, "%Y%m%d"
            ).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)

            if lastTradeDateTime > now:

                localSymbol = f"{cd.contract.localSymbol}-{cd.contract.lastTradeDateOrContractMonth}"
                symbolData = self.getHistoricalDataFromDB(
                    localSymbol, timeframe
                )

                if symbolData is not None:

                    # WE HAVE SOME DATA IN DB -> UPDATE
                    lastDateTime = symbolData.tail(1).index[0]

                    if now > lastDateTime:

                        timeBlocks = getTimeBlocks(
                            lastDateTime, now, maxBlockSize,
                        )

                        for timeBlock in timeBlocks:
                            result.append(
                                {
                                    "contract": cd.contract,
                                    "from": timeBlock[0],
                                    "to": timeBlock[1],
                                }
                            )
                else:

                    # OTHERWISE DOWNLOAD FULL
                    timeBlocks = getTimeBlocks(
                        datetime.strptime("19860101", "%Y%m%d").replace(tzinfo=timezone.utc),
                        now,
                        maxBlockSize,
                    )

                    for timeBlock in timeBlocks:
                        result.append(
                            {
                                "contract": cd.contract,
                                "from": timeBlock[0],
                                "to": timeBlock[1],
                            }
                        )

            else:
                log.info(
                    f" SKIPPED - {cd.contract.localSymbol} - {cd.contract.lastTradeDateOrContractMonth}"
                )

        return result

    def __downloadFutures(self, asset: Asset, maxBlockSize: int) -> List[Dict]:
        result = []

        for cd in asset.contractDetails:

            lastTradeDateTime = datetime.strptime(
                cd.contract.lastTradeDateOrContractMonth, "%Y%m%d"
            ).replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)

            if (
                lastTradeDateTime > datetime.strptime("19860101", "%Y%m%d").replace(tzinfo=timezone.utc)
                and lastTradeDateTime < now
            ):
                result.append(
                    {
                        "contract": cd.contract,
                        "from": lastTradeDateTime
                        - timedelta(days=maxBlockSize),
                        "to": lastTradeDateTime,
                    }
                )
            elif lastTradeDateTime >= now:
                result.append(
                    {
                        "contract": cd.contract,
                        "from": now - timedelta(days=maxBlockSize),
                        "to": now,
                    }
                )

        return result

    def __updateStock(
        self, asset: Asset, timeframe: TimeFrame, maxBlockSize: int
    ) -> List[Dict]:
        result = []

        contract = asset.contractDetails[0].contract
        symbolData = self.getHistoricalDataFromDB(asset.symbol, timeframe)

        now = datetime.now(timezone.utc)

        if symbolData is not None:

            # WE HAVE SOME DATA IN DB -> CHECK FOR SPLITS FIRST
            lastDateTime = symbolData.tail(1).index[0]

            # Check for stock splits since our last data point
            split_detected = self.__checkForSplits(
                contract, asset.symbol, lastDateTime, timeframe
            )

            if split_detected:
                # Split was detected and data was cleared
                # Do a full download from the beginning
                log.info(f"Re-downloading all data for {asset.symbol} due to split")
                timeBlocks = getTimeBlocks(
                    datetime.strptime("19860101", "%Y%m%d").replace(tzinfo=timezone.utc),
                    now,
                    maxBlockSize,
                )

                for timeBlock in timeBlocks:
                    result.append(
                        {
                            "contract": contract,
                            "from": timeBlock[0],
                            "to": timeBlock[1],
                        }
                    )
            elif now > lastDateTime:
                # No split, just update from last date
                timeBlocks = getTimeBlocks(lastDateTime, now, maxBlockSize,)

                for timeBlock in timeBlocks:
                    result.append(
                        {
                            "contract": contract,
                            "from": timeBlock[0],
                            "to": timeBlock[1],
                        }
                    )

        else:

            # OTHERWISE DOWNLOAD FULL
            timeBlocks = getTimeBlocks(
                datetime.strptime("19860101", "%Y%m%d").replace(tzinfo=timezone.utc), now, maxBlockSize,
            )

            for timeBlock in timeBlocks:
                result.append(
                    {
                        "contract": contract,
                        "from": timeBlock[0],
                        "to": timeBlock[1],
                    }
                )

        return result

    def __downloadStock(self, asset: Asset, maxBlockSize: int) -> List[Dict]:
        result = []

        contract = asset.contractDetails[0].contract

        timeBlocks = getTimeBlocks(
            datetime.strptime("19860101", "%Y%m%d").replace(tzinfo=timezone.utc),
            datetime.now(timezone.utc),
            maxBlockSize,
        )

        for timeBlock in timeBlocks:
            result.append(
                {
                    "contract": contract,
                    "from": timeBlock[0],
                    "to": timeBlock[1],
                }
            )

        return result

    # --------------------------------------------------------
    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------
    # --------------------------------------------------------

    # 1. - CUSTOM destroy -----------------------------------------
    def onDestroy(self):
        log.info("Destroying ...")

        if self.__currentThread is not None:
            self.__currentThread.terminate()

        # Close IB
        self.__ibClient.connectionClosed()  # close the EWrapper
        self.__ibClient.disconnect()  # close the EClient

    # 2. - Python destroy -----------------------------------------
    def __del__(self):
        log.info("Running ...")
