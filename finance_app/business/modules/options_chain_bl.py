"""
Business Logic layer for Options Chain page.
Handles IB connection and options chain data retrieval.
"""
import logging
import threading
import time
from typing import Any, List, Set

from rx import operators as ops
from rx.core.typing import Observable

from finance_app.business.model.contracts import (
    IBContract,
    IBOptionContract,
    IBStockContract,
)
from finance_app.business.services.ibclient.my_ib_client import MyIBClient
from finance_app.business.modules.asset_bl import AssetBL
from finance_app.business.model.asset import AssetType

# create logger
log = logging.getLogger("CellarLogger")


class OptionsChainBL(object):
    """Business Logic for Options Chain page"""

    def __init__(self):
        log.info("Running ...")

        # connect to IB
        self.ibClient = MyIBClient()

        # start thread
        self.ibClient_thread = threading.Thread(
            name=f"OptionsChainBL-ibClient-{self.ibClient.uid}-thread",
            target=lambda: self.ibClient.myStart(),
            daemon=True,
        )
        self.ibClient_thread.start()

        # Wait for connection to be established
        self._wait_for_connection()

        # Asset BL for getting contract details
        self.assetBl = AssetBL()

    def _wait_for_connection(self, timeout: int = 10):
        """Wait for IB client to connect"""
        start_time = time.time()
        while not self.ibClient.isConnected():
            if time.time() - start_time > timeout:
                log.error(f"IB client connection timeout after {timeout} seconds")
                break
            log.debug(f"Waiting for IB connection... (UID: {self.ibClient.uid})")
            time.sleep(0.5)

        if self.ibClient.isConnected():
            log.info(f"IB client connected (UID: {self.ibClient.uid})")

    def getOptionChainForSymbol(self, symbol: str) -> Observable:
        """
        Get option chain data (expirations and strikes) for a symbol.
        First resolves the contract to get conId, then gets the option chain.
        Returns Observable emitting dict with 'exchange', 'expirations', 'strikes'.
        """
        log.info(f"Getting option chain for symbol: {symbol}")
        log.info(f"IB client connected: {self.ibClient.isConnected()}, UID: {self.ibClient.uid}")

        # Check connection and wait if needed
        if not self.ibClient.isConnected():
            log.warning("IB client not connected, waiting...")
            self._wait_for_connection()

        # First try to get from DB (which has conId)
        asset = self.assetBl.get(AssetType.STOCK, symbol)
        if asset is not None and asset.contractDetails:
            contract = asset.contractDetails[0].contract
            log.info(f"Using contract from DB for {symbol}, conId: {contract.conId}")
            return self.ibClient.getOptionChain(contract).pipe(
                ops.filter(lambda x: x is not None),
                ops.filter(lambda x: x != {}),
                # Filter to only use SMART exchange which has the most complete data
                ops.filter(lambda x: x.get("exchange") == "SMART"),
                ops.take(1),  # Take only the first SMART exchange result
            )

        # If not in DB, need to get contract details from IB first
        log.info(f"Contract not in DB, fetching from IB for {symbol}")
        contract = IBStockContract()
        contract.symbol = symbol

        # Get contract details first, then get option chain
        return self.ibClient.getContractDetail(contract).pipe(
            ops.filter(lambda x: x is not None),
            ops.do_action(lambda x: log.info(f"Got contract details: {x.contract.symbol}, conId: {x.contract.conId}")),
            ops.flat_map(lambda contractDetails: self.ibClient.getOptionChain(contractDetails.contract)),
            ops.filter(lambda x: x is not None),
            ops.filter(lambda x: x != {}),
            # Filter to only use SMART exchange which has the most complete data
            ops.filter(lambda x: x.get("exchange") == "SMART"),
            ops.take(1),  # Take only the first SMART exchange result
        )

    def getOptionChain(self, contract: IBContract) -> Observable:
        """
        Get option chain data (expirations and strikes) for a contract.
        Contract must have a valid conId.
        Returns Observable emitting dict with 'exchange', 'expirations', 'strikes'.
        """
        log.debug(f"Getting option chain for {contract.symbol}, conId: {contract.conId}")
        return self.ibClient.getOptionChain(contract).pipe(
            ops.filter(lambda x: x is not None),
        )

    def getContractDetails(self, symbol: str) -> Observable:
        """
        Get contract details for a symbol from IB.
        Returns Observable emitting IBContractDetails.
        """
        contract = IBStockContract()
        contract.symbol = symbol
        return self.ibClient.getContractDetail(contract).pipe(
            ops.filter(lambda x: x is not None),
        )

    def getStockContract(self, symbol: str) -> IBStockContract:
        """
        Create a stock contract for the given symbol.
        """
        contract = IBStockContract()
        contract.symbol = symbol
        return contract

    def getStockContractFromDB(self, symbol: str):
        """
        Get stock contract from the asset database if it exists.
        """
        asset = self.assetBl.get(AssetType.STOCK, symbol)
        if asset is not None and asset.contractDetails:
            return asset.contractDetails[0].contract
        return None

    def startRealtimeOptions(self, contract: IBOptionContract) -> Observable:
        """
        Start real-time options data streaming for a specific option contract.
        Returns Observable emitting tick data with Greeks.
        """
        log.debug(f"Starting realtime options for {contract.symbol} {contract.strike} {contract.right}")
        return self.ibClient.startRealtimeOptions(contract).pipe(
            ops.filter(lambda x: x is not None),
        )

    def startRealtimeUnderlying(self, contract: IBContract) -> Observable:
        """
        Start real-time data streaming for the underlying stock.
        """
        log.debug(f"Starting realtime underlying for {contract.symbol}")
        return self.ibClient.startRealtimeData(contract).pipe(
            ops.filter(lambda x: x is not None),
        )

    def createOptionContract(
        self,
        symbol: str,
        expiration: str,
        strike: float,
        right: str,  # "C" for Call, "P" for Put
        exchange: str = "SMART",
        multiplier: int = 100,
    ) -> IBOptionContract:
        """
        Create an option contract for the given parameters.
        """
        contract = IBOptionContract()
        contract.symbol = symbol
        contract.exchange = exchange
        contract.lastTradeDateOrContractMonth = expiration
        contract.strike = strike
        contract.right = right
        contract.multiplier = multiplier
        # Don't set localSymbol - IB will resolve it
        return contract

    # --------------------------------------------------------
    # DESTROY
    # --------------------------------------------------------

    def onDestroy(self):
        log.info("Destroying ...")

        # Close IB
        self.ibClient.connectionClosed()
        self.ibClient.disconnect()

    def __del__(self):
        log.info("Running ...")
