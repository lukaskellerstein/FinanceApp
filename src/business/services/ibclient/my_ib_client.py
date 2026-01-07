import logging
import random
import time
from datetime import datetime
from typing import Any, List, Set, Tuple

from rx import Observable
from rx.core.typing import Observable

from src.business.model.contract_details import IBContractDetails
from src.business.model.contracts import (
    IBContract,
    IBFutureContract,
    IBStockContract,
)
from src.business.services.ibclient.state import State
from src.helpers import try_parsing_date
from ibapi.client import EClient
from ibapi.common import TickAttrib
from ibapi.contract import ContractDetails
from ibapi.ticktype import TickType, TickTypeEnum
from ibapi.wrapper import BarData, EWrapper
from src.business.model.factory.contract_factory import ContractFactory
from src.business.model.factory.contract_detail_factory import (
    ContractDetailsFactory,
)

from src.business.services.config_service import AppConfig

# from typings import ObservableType

# create logger
log = logging.getLogger("CellarLogger")


class MyIBClient(EWrapper, EClient):
    # state = State.getInstance()

    # data = []

    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self.uid = random.randint(1000, 10000)
        self.config = AppConfig()

        self.state = State.getInstance()

        log.info(f"uid: {self.uid}, state: {self.state.uid}")

        # Business object factory
        self.contractFactory = ContractFactory()
        self.contractDetailsFactory = ContractDetailsFactory()

    def myStart(self):
        log.info(f"----Connect & Run----{self.uid}")
        ip = self.config.twsIP()
        port = self.config.twsPort()
        self.connect(ip, int(port), self.uid)
        self.run()

    # --------------------------------------------------------------------
    # --------------------------------------------------------------------
    # OVERRIDE of EWrapper methods
    # --------------------------------------------------------------------
    # --------------------------------------------------------------------

    # --------------------------------------------------
    # OBSERVABLE VERSION
    # --------------------------------------------------
    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        log.debug(f"ContractDetails: {reqId}, details: {contractDetails}")

        obs: Observable[IBContractDetails] = self.state.getObservable(reqId)

        # log.debug(contractDetails)
        # # cast ContractDetails > IBContractDetails
        # aaa = obj_to_dict(contractDetails, ["secIdList"])
        # log.debug(aaa)
        # bbb = IBContractDetails(**aaa)
        # log.debug(bbb)

        # log.debug(IBStockContract(bbb.contract))

        # # convert Contract to right IBContract
        # if aaa["contract"]["secType"] == "STK":
        #     setattr(bbb, "contract", IBStockContract(bbb.contract))
        # elif aaa["contract"]["secType"] == "FUT":
        #     setattr(bbb, "contract", IBFutureContract(bbb.contract))
        # else:
        #     setattr(bbb, "contract", IBContract(bbb.contract))

        # log.debug(bbb)

        # ccc = IBContractDetails(contractDetails=contractDetails)
        # log.debug(ccc)

        # # convert Contract to right IBContract
        # if aaa["contract"]["secType"] == "STK":
        #     setattr(ccc, "contract", IBStockContract(bbb.contract))
        # elif aaa["contract"]["secType"] == "FUT":
        #     setattr(ccc, "contract", IBFutureContract(bbb.contract))
        # else:
        #     setattr(ccc, "contract", IBContract(bbb.contract))

        # log.debug(ccc)

        result = self.contractDetailsFactory.createIBContractDetails(
            contractDetails
        )
        obs.on_next(result)

    def historicalData(self, reqId: int, bar: BarData):
        log.info(
            f"HistoricalData [{self.uid}]. Ticker Id: {reqId}, Date: {bar.date}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Count: {bar.barCount}"
        )

        data = (
            try_parsing_date(bar.date, ["%Y%m%d", "%Y%m%d %H:%M:%S"]),
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            bar.volume,
        )

        self.state.addToTempData(reqId, data)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        log.info(
            f"{self.uid} - END - getHistoricalData. Ticker Id: {reqId}, start: {start}, end: {end}"
        )

        # (obs, symbol, localSymbol) = self.state.getObservableAndContract(reqId)

        # close observable
        # obs.on_completed()
        # obs.dispose()

        obs: Observable[Any] = self.state.getObservable(reqId)
        data: List[
            Tuple[datetime, float, float, float, float, float]
        ] = self.state.getTempData(reqId)

        # print(" ----------------------- WE GET DATA ----------------")
        # print(self.uid)
        # print(data)
        # print("------------------------------------------------------")

        obs.on_next(data)
        obs.on_completed()

    def fundamentalData(self, reqId: int, data: str):
        # super().fundamentalData(reqId, data)
        # print("FundamentalData. ReqId:", reqId, "Data:", data)

        obs: Observable[Any] = self.state.getObservable(reqId)
        obs.on_next(data)

    def securityDefinitionOptionParameter(
        self,
        reqId: int,
        exchange: str,
        underlyingConId: int,
        tradingClass: str,
        multiplier: str,
        expirations: Set[str],
        strikes: Set[float],
    ):
        log.info(f"OptionChain data received. reqId: {reqId}, exchange: {exchange}, expirations: {len(expirations)}, strikes: {len(strikes)}")

        obs: Observable[Any] = self.state.getObservable(reqId)

        if obs is not None:
            obs.on_next(
                {
                    "exchange": exchange,
                    "expirations": list(expirations),
                    "strikes": list(strikes),
                }
            )
        else:
            log.error(f"Observable not found for reqId: {reqId}")

    def securityDefinitionOptionParameterEnd(self, reqId: int):
        log.info(f"OptionChain data complete. reqId: {reqId}")

    def tickPrice(
        self, reqId: int, tickType: TickType, price: float, attrib: TickAttrib
    ):
        log.debug(
            f"tick-price. Ticker Id: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, price: {price}, attrib: {attrib}"
        )

        self.__tickData(reqId, tickType, price)

    def tickSize(self, reqId: int, tickType: TickType, size: int):
        log.debug(
            f"tick-size. Ticker Id: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, size: {size}"
        )

        self.__tickData(reqId, tickType, size)

    def tickString(self, reqId: int, tickType: TickType, value: str):
        log.debug(
            f"tick-string. Ticker Id: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, value: {value}"
        )

        self.__tickData(reqId, tickType, value)

    def tickGeneric(self, reqId: int, tickType: TickType, value: float):
        log.debug(
            f"tick-generic. Ticker Id: {reqId}, tickType: {TickTypeEnum.to_str(tickType)}, value: {value}"
        )

        self.__tickData(reqId, tickType, value)

    # region tickData helper methods

    def __tickData(self, reqId: int, tickType: TickType, value: Any):

        (obs, symbol, localSymbol) = self.state.getObservableAndContract(reqId)

        # If no contract info found, try to get observable directly
        # (this happens for options which use registerOnlyNewObservable)
        if obs is None:
            obs = self.state.getObservable(reqId)
            if obs is None:
                log.debug(f"No observable found for reqId: {reqId}")
                return

        obs.on_next(
            {
                "ticker": symbol,
                "localSymbol": localSymbol,
                "type": TickTypeEnum.to_str(tickType).lower(),
                "price": value,
            }
        )

    # endregion

    def tickOptionComputation(
        self,
        reqId: int,
        tickType: TickType,
        tickAttrib: int,  # New parameter in updated IB API
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float,
    ):
        # Get contract info if available
        contract_info = ""
        if hasattr(self, '_optionReqIdMap') and reqId in self._optionReqIdMap:
            contract_info = f" [{self._optionReqIdMap[reqId]}]"

        log.debug(f"tickOptionComputation - reqId: {reqId}{contract_info}, tickType: {TickTypeEnum.to_str(tickType)}, optPrice: {optPrice}, delta: {delta}")

        obs: Observable[Any] = self.state.getObservable(reqId)

        if obs is not None:
            obs.on_next(
                {
                    "tickType": TickTypeEnum.to_str(tickType),
                    "impliedVolatility": impliedVol,
                    "optPrice": optPrice,
                    "undPrice": undPrice,
                    "pvDividend": pvDividend,
                    "delta": delta,
                    "gamma": gamma,
                    "vega": vega,
                    "theta": theta,
                }
            )
        else:
            log.warning(f"No observable found for reqId: {reqId}")

        # (obs, symbol, localSymbol) = self.state.getObservableAndContract(reqId)

        # obs.on_next(
        #     {
        #         "ticker": symbol,
        #         "localSymbol": localSymbol,
        #         "tickType": TickTypeEnum.to_str(tickType),
        #         "impliedVolatility": impliedVolatility,
        #         "optPrice": optPrice,
        #         "undPrice": undPrice,
        #         "pvDividend": pvDividend,
        #         "delta": delta,
        #         "gamma": gamma,
        #         "vega": vega,
        #         "theta": theta,
        #     }
        # )

    def error(self, reqId: int, errorCode: int, errorString: str):
        # Get contract info if available
        contract_info = ""
        if hasattr(self, '_optionReqIdMap') and reqId in self._optionReqIdMap:
            contract_info = f" [{self._optionReqIdMap[reqId]}]"

        # Informational messages (not real errors)
        if errorCode in [2104, 2106, 2108, 2158]:
            log.info(f"reqId: {reqId}{contract_info}, code: {errorCode}, text: {errorString}")
        # Market data farm connection messages
        elif errorCode in [2119, 2157]:
            log.info(f"reqId: {reqId}{contract_info}, code: {errorCode}, text: {errorString}")
        # No trading permissions or no market data subscription - expected for some options
        elif errorCode in [10167, 10168, 354]:
            log.warning(f"reqId: {reqId}{contract_info}, code: {errorCode}, text: {errorString}")
        # No security definition - option contract not found (common for illiquid strikes)
        elif errorCode == 200:
            log.warning(f"No security definition for reqId: {reqId}{contract_info} - {errorString}")
        else:
            log.error(f"reqId: {reqId}{contract_info}, errorCode: {errorCode}, errorText: {errorString}")

        if reqId != -1:
            obs: Observable[Any] = self.state.getObservable(reqId)
            if obs is not None:
                obs.on_next({})

    # --------------------------------------------------------------------
    # --------------------------------------------------------------------
    # CUSTOM METHODS
    # --------------------------------------------------------------------
    # --------------------------------------------------------------------

    def getFundamentalData(self, contract: IBContract) -> Observable:
        log.debug(f"STARTS - getFundamentalData - UID: {str(self.uid)}")

        (reqId, obs) = self.state.registerOnlyNewObservable()

        self.reqFundamentalData(reqId, contract, "CalendarReport", [])

        return obs

    def getHistoricalData(
        self,
        contract: IBContract,
        endDateTime: str = "",
        duration: str = "10 D",
        barSize: str = "1 day",
        priceType: str = "MIDPOINT",
    ) -> Observable[List[Tuple[datetime, float, float, float, float, float]]]:
        log.debug(f"STARTS - getHistoricalData - UID: {str(self.uid)}")

        (reqId, obs) = self.state.registerOnlyNewObservable()

        log.info(
            f"startHistorical for {contract.symbol}-{contract.localSymbol}-{contract.lastTradeDateOrContractMonth} : reqId={reqId}"
        )

        self.state.registerTempData(reqId, [])

        self.reqHistoricalData(
            reqId,
            contract,
            endDateTime,
            duration,
            barSize,
            priceType,
            1,
            1,
            False,
            [],
        )

        return obs

    def getContractDetail(
        self, contract: IBContract
    ) -> Observable[IBContractDetails]:
        log.debug(f"STARTS - getContractDetail - UID: {str(self.uid)}")

        (reqId, obs) = self.state.registerOnlyNewObservable()

        self.reqContractDetails(reqId, contract)

        return obs

    def startRealtimeData(self, contract: IBContract) -> Observable[Any]:
        log.debug(f"STARTS - startRealtimeData - UID: {str(self.uid)}")

        (isExist, reqId, obs) = self.state.observableForContract(
            contract, "tickPriceEvent"
        )

        # print(isExist)
        # print(reqId)
        # print(obs)
        # self.state.log()
        log.debug("______________")
        log.debug(
            f"startRealtime for {contract.symbol}-{contract.localSymbol} : reqId={reqId}"
        )
        log.debug("______________")

        if isExist == False:
            self.reqMarketDataType(1)
            self.reqMktData(reqId, contract, "456,104,106", False, False, [])

        return obs

    def stopRealtimeData(self, contract: IBContract):
        log.debug(f"START - stopRealtimeData - UID: {str(self.uid)}")

        (isExist, reqId, obs) = self.state.getObservableForContract(
            contract, "tickPriceEvent"
        )

        if isExist == True:
            # cancel IB streaming of data
            self.cancelMktData(reqId)

            # close observable
            obs.on_completed()
            obs.dispose()

            self.state.removeObservable(reqId, contract, "tickPriceEvent")
        else:
            print("-----------------------------------------------")
            print("-----------------------------------------------")
            print("-----------------------------------------------")
            print("ERROR - OBSERVABLE DOESN'T EXIST")
            print("-----------------------------------------------")
            print("-----------------------------------------------")
            print("-----------------------------------------------")

    # ----------------------------------------------------
    # ----------------------------------------------------
    # OPTIONS
    # ----------------------------------------------------
    # ----------------------------------------------------

    def getOptionChain(self, contract: IBContract) -> Observable[Any]:
        log.info(f"STARTS - getOptionChain - UID: {str(self.uid)}, symbol: {contract.symbol}, conId: {contract.conId}")

        (reqId, obs) = self.state.registerOnlyNewObservable()

        log.info(f"Calling reqSecDefOptParams - reqId: {reqId}, symbol: {contract.symbol}, secType: {contract.secType}, conId: {contract.conId}")
        self.reqSecDefOptParams(
            reqId, contract.symbol, "", contract.secType, contract.conId,
        )

        return obs

    def getOptionPrice(
        self,
        contract: IBContract,
        volatility: float,
        underPrice: float,
        timeout: int,
    ) -> Observable[Any]:
        log.info("Running ...")

        # print(contract)
        # print(f"vol:{volatility}, price:{underPrice}")
        # print(timeout)

        time.sleep(timeout)

        (reqId, obs) = self.state.registerOnlyNewObservable()
        # print(reqId)

        # optionContract = LlOption("AAPL")
        # optionContract.exchange = "SMART"
        # optionContract.lastTradeDateOrContractMonth = "20200501"
        # optionContract.strike = 310.0
        # optionContract.right = "C"  # CALL OPTION
        # optionContract.multiplier = 100

        # vol = 0.48
        # uP = 320.0

        self.calculateOptionPrice(reqId, contract, volatility, underPrice, [])

        return obs

    def startRealtimeOptions(self, contract: IBContract) -> Observable[Any]:
        log.debug(f"STARTS - startRealtimeOptions - UID: {str(self.uid)}")

        # Always create a new observable for each option contract
        # (don't reuse by symbol since each option has different strike/expiration/right)
        (reqId, obs) = self.state.registerOnlyNewObservable()

        log.info(
            f"startRealtimeOptions for {contract.symbol} {contract.lastTradeDateOrContractMonth} "
            f"strike={contract.strike} right={contract.right} : reqId={reqId}"
        )

        # Store the contract info for debugging
        self._optionReqIdMap = getattr(self, '_optionReqIdMap', {})
        self._optionReqIdMap[reqId] = f"{contract.symbol} {contract.lastTradeDateOrContractMonth} strike={contract.strike} right={contract.right}"

        self.reqMarketDataType(1)
        self.reqMktData(reqId, contract, "", False, False, [])

        return obs

    def stopRealtimeOptions(self):
        # TBD
        pass

    # Python destroy -----------------------------------------
    def __del__(self):
        log.info(f"Running ...{self.uid}")
        print(f"isConnected: {self.isConnected()}")
