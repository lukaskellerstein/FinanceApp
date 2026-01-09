"""
Interactive Brokers client implementation.

Refactored to use:
- MarketDataBridge for thread-safe UI communication
- IBState for request management
- Domain types instead of ibapi types at the interface
- Callback-based API instead of RxPy observables
"""

from __future__ import annotations
import logging
import random
import threading
import xml.etree.ElementTree as ET
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from ibapi.client import EClient
from ibapi.common import TickAttrib, WshEventData
from ibapi.contract import Contract as IBApiContract
from ibapi.contract import ContractDetails as IBApiContractDetails
from ibapi.ticktype import TickType, TickTypeEnum
from ibapi.wrapper import BarData as IBApiBarData, EWrapper

from src.core.interfaces.broker import IBrokerClient
from src.core.config.app_config import AppConfig
from src.domain.entities.contract import Contract
from src.domain.entities.contract_details import ContractDetails
from src.domain.value_objects.bar_data import BarData
from src.domain.value_objects.tick_data import TickData
from src.infrastructure.broker.ib_state import IBState
from src.infrastructure.broker.ib_mappers import IBMapper
from src.presentation.state.market_data_bridge import MarketDataBridge

log = logging.getLogger("CellarLogger")


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class IBClient(EWrapper, EClient, IBrokerClient):
    """
    Interactive Brokers client implementation.

    This class implements the IBrokerClient interface and provides
    thread-safe communication with the UI layer via MarketDataBridge.

    Key features:
    - Implements standard IBrokerClient interface for DI
    - Uses callback-based API for async results
    - Thread-safe UI updates via MarketDataBridge
    - Decoupled from ibapi types at the interface level

    Example:
        bridge = MarketDataBridge()
        client = IBClient(bridge)
        client.connect()

        # Get contract details
        def on_details(details: ContractDetails):
            print(f"Got details: {details.long_name}")

        client.get_contract_details(contract, on_details)
    """

    def __init__(
        self,
        market_data_bridge: MarketDataBridge,
        config: Optional[AppConfig] = None,
        state: Optional[IBState] = None,
    ):
        """
        Initialize IB client.

        Args:
            market_data_bridge: Bridge for thread-safe UI communication
            config: Application configuration (optional, creates default)
            state: Request state manager (optional, creates default)
        """
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        self.uid = random.randint(1000, 10000)
        self.config = config or AppConfig()
        self.state = state or IBState()
        self.bridge = market_data_bridge
        self.mapper = IBMapper()

        # Connection state tracking
        self._connection_state = ConnectionState.DISCONNECTED
        self._connected_event = threading.Event()
        self._next_order_id: Optional[int] = None
        self._connection_error: Optional[str] = None

        # Track option request info for debugging
        self._option_req_map: Dict[int, str] = {}

        log.info(f"IBClient initialized with uid: {self.uid}")

    # ----------------------------------------------------------------
    # IBrokerClient Interface Implementation
    # ----------------------------------------------------------------

    def connect(self) -> None:
        """Connect to IB Gateway/TWS."""
        log.info(f"Connecting IBClient {self.uid}")
        self._connection_state = ConnectionState.CONNECTING
        self._connected_event.clear()
        self._connection_error = None

        broker_config = self.config.broker_config
        ip = broker_config.ip
        port = broker_config.port
        log.info(f"Connecting to IB at {ip}:{port}")
        EClient.connect(self, ip, port, self.uid)

    def start(self) -> None:
        """Start the client message loop (blocking)."""
        log.info(f"Starting IBClient {self.uid}")
        self.run()

    def disconnect(self) -> None:
        """Disconnect from broker."""
        log.info(f"Disconnecting IBClient {self.uid}")
        self._connection_state = ConnectionState.DISCONNECTED
        self._connected_event.clear()
        EClient.disconnect(self)

    def is_connected(self) -> bool:
        """Check if connected to broker (socket and handshake complete)."""
        return (
            self._connection_state == ConnectionState.CONNECTED
            and self.isConnected()
        )

    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """
        Wait for connection to be established.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if connected, False if timeout or error
        """
        import time
        start = time.time()

        # Give socket time to settle (initial connect may take a moment)
        time.sleep(0.2)

        while time.time() - start < timeout:
            # Check if already connected
            if self._connection_state == ConnectionState.CONNECTED:
                return True

            # Check if error occurred
            if self._connection_state == ConnectionState.ERROR:
                return False

            # Check if event is set (connection succeeded or error occurred)
            if self._connected_event.wait(timeout=0.5):
                return self._connection_state == ConnectionState.CONNECTED

            # Check if socket disconnected without triggering callback
            # (e.g., TWS not running - socket fails to connect)
            if (
                self._connection_state == ConnectionState.CONNECTING
                and not self.isConnected()
            ):
                self._connection_state = ConnectionState.ERROR
                self._connection_error = "Socket connection failed - is TWS/Gateway running?"
                log.warning(self._connection_error)
                return False

        # Timeout
        if self._connection_state == ConnectionState.CONNECTING:
            self._connection_state = ConnectionState.ERROR
            self._connection_error = "Connection timeout"
        return False

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def connection_error(self) -> Optional[str]:
        """Get last connection error message."""
        return self._connection_error

    def get_contract_details(
        self,
        contract: Contract,
        callback: Optional[Callable[[ContractDetails], None]] = None,
    ) -> int:
        """
        Get contract details from broker.

        Args:
            contract: Domain contract to look up
            callback: Called with ContractDetails when received

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        ib_contract = self.mapper.to_ib_contract(contract)
        self.reqContractDetails(req_id, ib_contract)

        log.info(f"Requested contract details: req_id={req_id}, symbol={contract.symbol}, secType={contract.sec_type}, exchange={contract.exchange}")
        return req_id

    def get_historical_data(
        self,
        contract: Contract,
        end_datetime: Optional[datetime] = None,
        duration: str = "10 D",
        bar_size: str = "1 day",
        price_type: str = "MIDPOINT",
        callback: Optional[Callable[[List[BarData]], None]] = None,
    ) -> int:
        """
        Get historical OHLCV data.

        Args:
            contract: Contract to get data for
            end_datetime: End date/time (empty string = now)
            duration: Duration string (e.g., "365 D")
            bar_size: Bar size string (e.g., "1 day")
            price_type: Price type (e.g., "TRADES", "MIDPOINT")
            callback: Called with List[BarData] when complete

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        # Initialize temp data for accumulating bars
        self.state.init_temp_data(req_id)

        ib_contract = self.mapper.to_ib_contract(contract)
        end_dt_str = end_datetime.strftime("%Y%m%d %H:%M:%S") if end_datetime else ""

        self.reqHistoricalData(
            req_id,
            ib_contract,
            end_dt_str,
            duration,
            bar_size,
            price_type,
            1,  # useRTH
            1,  # formatDate
            False,  # keepUpToDate
            [],  # chartOptions
        )

        log.info(
            f"Requested historical data: req_id={req_id}, "
            f"symbol={contract.symbol}, duration={duration}, bar_size={bar_size}"
        )
        return req_id

    def subscribe_realtime(
        self,
        contract: Contract,
        callback: Optional[Callable[[TickData], None]] = None,
    ) -> int:
        """
        Subscribe to real-time market data.

        Args:
            contract: Contract to subscribe to
            callback: Called with TickData on each update

        Returns:
            Request ID
        """
        # Check if already subscribed
        existed, req_id = self.state.get_or_create_request_for_contract(
            contract, "tickPrice"
        )

        if callback:
            self.state.register_callback(req_id, callback)

        if not existed:
            ib_contract = self.mapper.to_ib_contract(contract)
            # Use market data type 4 (delayed frozen) to get data during off-hours
            # Type 4 returns: live when available, delayed when live not available,
            # frozen when market closed, delayed frozen as last resort
            self.reqMarketDataType(4)
            self.reqMktData(req_id, ib_contract, "456,104,106", False, False, [])

            log.info(f"Subscribed to realtime: req_id={req_id}, symbol={contract.symbol}, local_symbol={contract.local_symbol}")
        else:
            log.debug(f"Already subscribed: req_id={req_id}, symbol={contract.symbol}")

        return req_id

    def unsubscribe_realtime(self, contract: Contract) -> None:
        """
        Unsubscribe from real-time market data.

        Args:
            contract: Contract to unsubscribe from
        """
        req_id = self.state.get_request_for_contract(contract, "tickPrice")

        if req_id:
            self.cancelMktData(req_id)
            self.state.remove_request(req_id)
            log.info(f"Unsubscribed from realtime: req_id={req_id}, symbol={contract.symbol}")
        else:
            log.warning(f"No subscription found for {contract.symbol}")

    def get_fundamental_data(
        self,
        contract: Contract,
        report_type: str = "CalendarReport",
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """
        Get fundamental data (XML).

        Args:
            contract: Contract to get data for
            report_type: Type of report
            callback: Called with XML string

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        ib_contract = self.mapper.to_ib_contract(contract)
        self.reqFundamentalData(req_id, ib_contract, report_type, [])

        log.debug(f"Requested fundamental data: req_id={req_id}, report={report_type}")
        return req_id

    def get_option_chain(
        self,
        contract: Contract,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> int:
        """
        Get option chain parameters.

        Args:
            contract: Underlying contract
            callback: Called with option chain data

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        log.info(
            f"Requesting option chain: req_id={req_id}, "
            f"symbol={contract.symbol}, conId={contract.con_id}"
        )
        self.reqSecDefOptParams(
            req_id,
            contract.symbol,
            "",
            contract.sec_type,
            contract.con_id,
        )

        return req_id

    def subscribe_option_realtime(
        self,
        contract: Contract,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> int:
        """
        Subscribe to option real-time data.

        Args:
            contract: Option contract
            callback: Called with option tick data

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        # Store contract info for debugging
        self._option_req_map[req_id] = (
            f"{contract.symbol} {contract.last_trade_date} "
            f"strike={contract.strike} right={contract.right}"
        )

        ib_contract = self.mapper.to_ib_contract(contract)
        self.reqMarketDataType(1)
        self.reqMktData(req_id, ib_contract, "", False, False, [])

        log.info(f"Subscribed to option realtime: req_id={req_id}")
        return req_id

    def get_wsh_meta_data(
        self,
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """
        Get Wall Street Horizon metadata (available event types).

        Args:
            callback: Called with JSON string containing event type info

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        self.reqWshMetaData(req_id)

        log.info(f"Requested WSH metadata: req_id={req_id}")
        return req_id

    def get_wsh_event_data(
        self,
        con_id: int,
        start_date: str = "",
        end_date: str = "",
        limit: int = 100,
        callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        """
        Get Wall Street Horizon calendar events.

        Args:
            con_id: Contract ID to get events for
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
            limit: Maximum number of events to return
            callback: Called with JSON string containing events

        Returns:
            Request ID
        """
        req_id = self.state.next_request_id()

        if callback:
            self.state.register_callback(req_id, callback)

        wsh_data = WshEventData()
        wsh_data.conId = con_id
        wsh_data.startDate = start_date
        wsh_data.endDate = end_date
        wsh_data.totalLimit = limit

        self.reqWshEventData(req_id, wsh_data)

        log.info(f"Requested WSH events: req_id={req_id}, con_id={con_id}")
        return req_id

    # ----------------------------------------------------------------
    # EWrapper Callbacks
    # ----------------------------------------------------------------

    def nextValidId(self, orderId: int) -> None:
        """
        Called when connection is established and IB sends the next valid order ID.

        This callback confirms the connection handshake is complete.
        """
        super().nextValidId(orderId)
        self._next_order_id = orderId
        self._connection_state = ConnectionState.CONNECTED
        self._connected_event.set()
        log.info(f"Connection confirmed - next valid order ID: {orderId}")

    def connectionClosed(self) -> None:
        """Called when connection is closed."""
        super().connectionClosed()
        self._connection_state = ConnectionState.DISCONNECTED
        self._connected_event.clear()
        log.info("Connection to IB closed")

    def contractDetails(self, reqId: int, contractDetails: IBApiContractDetails):
        """Handle contract details response."""
        log.info(f"ContractDetails received: req_id={reqId}, symbol={contractDetails.contract.symbol}, secType={contractDetails.contract.secType}, exchange={contractDetails.contract.exchange}")

        domain_details = self.mapper.from_ib_contract_details(contractDetails)

        # Call callback if registered
        callback = self.state.get_callback(reqId)
        if callback:
            callback(domain_details)

    def contractDetailsEnd(self, reqId: int):
        """Handle end of contract details."""
        log.debug(f"ContractDetailsEnd: req_id={reqId}")
        # Cleanup can be done here if needed

    def historicalData(self, reqId: int, bar: IBApiBarData):
        """Handle individual historical bar."""
        log.debug(
            f"HistoricalData: req_id={reqId}, date={bar.date}, "
            f"O={bar.open}, H={bar.high}, L={bar.low}, C={bar.close}, V={bar.volume}"
        )

        domain_bar = self.mapper.from_ib_bar(bar)
        self.state.add_temp_data(reqId, domain_bar)

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        """Handle end of historical data."""
        log.info(f"HistoricalDataEnd: req_id={reqId}, start={start}, end={end}")

        bars = self.state.get_temp_data(reqId)
        self.state.clear_temp_data(reqId)

        callback = self.state.get_callback(reqId)
        if callback:
            callback(bars)

    def fundamentalData(self, reqId: int, data: str):
        """Handle fundamental data response."""
        log.debug(f"FundamentalData received: req_id={reqId}, len={len(data)}")

        callback = self.state.get_callback(reqId)
        if callback:
            callback(data)

    def wshMetaData(self, reqId: int, dataJson: str):
        """Handle WSH metadata response."""
        log.info(f"WSH metadata received: req_id={reqId}, len={len(dataJson)}")

        callback = self.state.get_callback(reqId)
        if callback:
            callback(dataJson)

    def wshEventData(self, reqId: int, dataJson: str):
        """Handle WSH event data response."""
        log.info(f"WSH event data received: req_id={reqId}, len={len(dataJson)}")

        callback = self.state.get_callback(reqId)
        if callback:
            callback(dataJson)

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
        """Handle option chain data."""
        log.info(
            f"OptionChain: req_id={reqId}, exchange={exchange}, "
            f"expirations={len(expirations)}, strikes={len(strikes)}"
        )

        callback = self.state.get_callback(reqId)
        if callback:
            callback({
                "exchange": exchange,
                "underlying_con_id": underlyingConId,
                "trading_class": tradingClass,
                "multiplier": multiplier,
                "expirations": list(expirations),
                "strikes": list(strikes),
            })

    def securityDefinitionOptionParameterEnd(self, reqId: int):
        """Handle end of option chain data."""
        log.info(f"OptionChainEnd: req_id={reqId}")

    def tickPrice(
        self, reqId: int, tickType: TickType, price: float, attrib: TickAttrib
    ):
        """Handle price tick."""
        self._handle_tick(reqId, tickType, price)

    def tickSize(self, reqId: int, tickType: TickType, size: int):
        """Handle size tick."""
        self._handle_tick(reqId, tickType, size)

    def tickString(self, reqId: int, tickType: TickType, value: str):
        """Handle string tick."""
        self._handle_tick(reqId, tickType, value)

    def tickGeneric(self, reqId: int, tickType: TickType, value: float):
        """Handle generic tick."""
        self._handle_tick(reqId, tickType, value)

    def _handle_tick(self, reqId: int, tickType: TickType, value: Any):
        """Common tick handler."""
        tick_name = TickTypeEnum.toStr(tickType).lower()
        log.debug(f"Tick: req_id={reqId}, type={tick_name}, value={value}")

        symbol, local_symbol = self.state.get_contract_info(reqId)

        # Send via bridge for thread-safe UI update
        if symbol:
            self.bridge.post_tick_update(
                symbol=symbol,
                local_symbol=local_symbol,
                tick_type=tick_name,
                value=value,
            )

        # Also call callback if registered
        callback = self.state.get_callback(reqId)
        if callback:
            callback({
                "symbol": symbol,
                "local_symbol": local_symbol,
                "tick_type": tick_name,
                "value": value,
            })

    def tickOptionComputation(
        self,
        reqId: int,
        tickType: TickType,
        tickAttrib: int,
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float,
    ):
        """Handle option computation tick."""
        tick_name = TickTypeEnum.toStr(tickType)
        log.debug(f"OptionComputation: req_id={reqId}, type={tick_name}, price={optPrice}")

        callback = self.state.get_callback(reqId)
        if callback:
            callback({
                "tick_type": tick_name,
                "implied_volatility": impliedVol,
                "option_price": optPrice,
                "underlying_price": undPrice,
                "pv_dividend": pvDividend,
                "delta": delta,
                "gamma": gamma,
                "vega": vega,
                "theta": theta,
            })

    def error(self, reqId: int, errorTime: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """Handle errors from IB."""
        contract_info = self._option_req_map.get(reqId, "")
        if contract_info:
            contract_info = f" [{contract_info}]"

        # Categorize errors
        info_codes = [2104, 2106, 2108, 2158, 2119, 2157]
        warning_codes = [10167, 10168, 354, 2174, 2176]
        no_data_codes = [162, 165, 166, 200, 366]
        connection_error_codes = [502, 504, 1100, 1101, 1102]  # Connection-related errors

        # Handle connection errors
        if errorCode in connection_error_codes:
            self._connection_error = errorString
            self._connection_state = ConnectionState.ERROR
            self._connected_event.set()  # Unblock any waiters
            log.error(f"IB Connection Error: code={errorCode}: {errorString}")
            return

        if errorCode in info_codes:
            log.info(f"IB Info: req_id={reqId}{contract_info}, code={errorCode}: {errorString}")
        elif errorCode in warning_codes:
            log.warning(f"IB Warning: req_id={reqId}{contract_info}, code={errorCode}: {errorString}")
        elif errorCode in no_data_codes:
            log.warning(f"IB No Data: req_id={reqId}{contract_info}, code={errorCode}: {errorString}")
            # Emit error info to help diagnose issues
            print(f"[IB ERROR] No Data: req_id={reqId}, code={errorCode}: {errorString}", flush=True)
            # Emit None to signal no data (callback expects ContractDetails or None)
            callback = self.state.get_callback(reqId)
            if callback:
                callback(None)
        else:
            log.error(f"IB Error: req_id={reqId}{contract_info}, code={errorCode}: {errorString}")
            callback = self.state.get_callback(reqId)
            if callback:
                callback(None)

    # ----------------------------------------------------------------
    # Utility Methods
    # ----------------------------------------------------------------

    def get_split_history(
        self,
        contract: Contract,
        callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
    ) -> int:
        """
        Get stock split history from fundamental data.

        Args:
            contract: Contract to get splits for
            callback: Called with list of split info dicts

        Returns:
            Request ID
        """

        def parse_splits(xml_data: str) -> List[Dict[str, Any]]:
            """Parse CalendarReport XML for split info."""
            splits = []
            if not xml_data or not isinstance(xml_data, str):
                return splits

            try:
                root = ET.fromstring(xml_data)

                for split_info in root.findall(".//SplitInfo"):
                    for split in split_info.findall(".//Split"):
                        self._parse_split_element(split, splits)

                for stock_split in root.findall(".//StockSplit"):
                    self._parse_stock_split_element(stock_split, splits)

            except ET.ParseError as e:
                log.warning(f"XML parse error: {e}")
            except Exception as e:
                log.warning(f"Error parsing splits: {e}")

            splits.sort(key=lambda x: x["date"], reverse=True)
            return splits

        def on_fundamental(data: str):
            if callback:
                callback(parse_splits(data))

        return self.get_fundamental_data(contract, "CalendarReport", on_fundamental)

    def _parse_split_element(
        self, element: ET.Element, splits: List[Dict[str, Any]]
    ) -> None:
        """Parse a Split element."""
        try:
            date_str = element.get("Date") or element.findtext("Date")
            ratio_str = element.get("Ratio") or element.findtext("Ratio")
            desc = element.get("Description") or element.findtext("Description") or ""

            if date_str and ratio_str:
                split_date = self._parse_date(date_str)
                if split_date:
                    ratio = self._parse_ratio(ratio_str)
                    splits.append({
                        "date": split_date,
                        "ratio": ratio,
                        "description": desc,
                    })
        except Exception as e:
            log.warning(f"Error parsing split: {e}")

    def _parse_stock_split_element(
        self, element: ET.Element, splits: List[Dict[str, Any]]
    ) -> None:
        """Parse a StockSplit element."""
        try:
            date_str = element.get("ExDate") or element.findtext("ExDate")
            ratio_str = element.get("SplitRatio") or element.findtext("SplitRatio")

            if date_str and ratio_str:
                split_date = self._parse_date(date_str)
                if split_date:
                    ratio = self._parse_ratio(str(ratio_str))
                    splits.append({
                        "date": split_date,
                        "ratio": ratio,
                        "description": f"Stock split {ratio_str}",
                    })
        except Exception as e:
            log.warning(f"Error parsing stock split: {e}")

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def _parse_ratio(self, ratio_str: str) -> float:
        """Parse split ratio string."""
        try:
            if ":" in ratio_str:
                parts = ratio_str.split(":")
                return float(parts[0]) / float(parts[1])
            elif "-" in ratio_str:
                parts = ratio_str.split("-")
                return float(parts[0]) / float(parts[1])
            else:
                return float(ratio_str)
        except (ValueError, ZeroDivisionError):
            return 1.0

    def __del__(self):
        """Cleanup on destruction."""
        log.info(f"IBClient {self.uid} destroyed")
