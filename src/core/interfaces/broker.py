"""
Broker client interface for Interactive Brokers integration.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime


class IBrokerClient(ABC):
    """
    Abstract interface for broker client operations.

    Implemented by IBClient in infrastructure layer.
    Uses callback-based async pattern for results.

    Example:
        client: IBrokerClient = container.resolve(IBrokerClient)
        client.connect()

        def on_data(bars: List[BarData]):
            print(f"Received {len(bars)} bars")

        client.get_historical_data(contract, callback=on_data)
    """

    @abstractmethod
    def connect(self) -> None:
        """Connect to the broker."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the client message loop (blocking)."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the broker."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to broker."""
        pass

    @abstractmethod
    def wait_for_connection(self, timeout: float = 10.0) -> bool:
        """
        Wait for connection to be established.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if connected, False if timeout or error
        """
        pass

    @property
    @abstractmethod
    def connection_error(self) -> Optional[str]:
        """Get last connection error message."""
        pass

    # Contract Details
    @abstractmethod
    def get_contract_details(
        self,
        contract: Any,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> int:
        """
        Get contract details from broker.

        Args:
            contract: Domain Contract to look up
            callback: Called with ContractDetails when received

        Returns:
            Request ID
        """
        pass

    # Historical Data
    @abstractmethod
    def get_historical_data(
        self,
        contract: Any,
        end_datetime: Optional[datetime] = None,
        duration: str = "10 D",
        bar_size: str = "1 day",
        price_type: str = "TRADES",
        callback: Optional[Callable[[List[Any]], None]] = None,
    ) -> int:
        """
        Get historical OHLCV data.

        Args:
            contract: Contract to get data for
            end_datetime: End date/time for the data (None = now)
            duration: Duration string (e.g., "365 D")
            bar_size: Bar size string (e.g., "1 day")
            price_type: Price type (e.g., "TRADES", "MIDPOINT")
            callback: Called with List[BarData] when complete

        Returns:
            Request ID
        """
        pass

    # Real-time Data
    @abstractmethod
    def subscribe_realtime(
        self,
        contract: Any,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> int:
        """
        Subscribe to real-time market data.

        Args:
            contract: Contract to subscribe to
            callback: Called with TickData on each update

        Returns:
            Request ID
        """
        pass

    @abstractmethod
    def unsubscribe_realtime(self, contract: Any) -> None:
        """
        Unsubscribe from real-time market data.

        Args:
            contract: Contract to unsubscribe from
        """
        pass

    # Fundamental Data
    @abstractmethod
    def get_fundamental_data(
        self,
        contract: Any,
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
        pass

    # Options
    @abstractmethod
    def get_option_chain(
        self,
        contract: Any,
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
        pass

    @abstractmethod
    def subscribe_option_realtime(
        self,
        contract: Any,
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
        pass
