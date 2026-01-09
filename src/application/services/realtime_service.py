"""
Real-time data service implementation.

Provides business logic for real-time market data streaming with DI.
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.services import IRealtimeService, IAssetService
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.contract import Contract
from src.domain.value_objects.tick_data import TickData
from src.presentation.state.market_data_bridge import MarketDataBridge

log = logging.getLogger("CellarLogger")


class TickUpdate(QObject):
    """Qt signal emitter for tick updates."""

    tick_received = pyqtSignal(str, str, object)  # symbol, local_symbol, TickData


class RealtimeService(IRealtimeService):
    """
    Real-time data service with dependency injection.

    Provides:
    - Subscribe to real-time market data
    - Unsubscribe from data streams
    - Track active subscriptions

    Uses MarketDataBridge for thread-safe UI updates.

    Example:
        service = RealtimeService(
            broker_client=ib_client,
            market_data_bridge=bridge,
            asset_service=asset_service,
        )
        service.subscribe("STOCK", "AAPL")
    """

    def __init__(
        self,
        broker_client: IBrokerClient,
        market_data_bridge: MarketDataBridge,
        asset_service: Optional[IAssetService] = None,
    ):
        """
        Initialize service.

        Args:
            broker_client: Broker client for data streaming
            market_data_bridge: Bridge for thread-safe tick updates
            asset_service: Optional asset service for contract lookup
        """
        self._broker = broker_client
        self._bridge = market_data_bridge
        self._asset_service = asset_service

        # Track subscriptions: (asset_type, symbol) -> req_id
        self._subscriptions: Dict[tuple, int] = {}
        self._lock = threading.Lock()

        # Track tick data per symbol
        self._tick_data: Dict[str, Dict[str, Any]] = {}

        log.info("RealtimeService initialized")

    # ----------------------------------------------------------------
    # IRealtimeService Implementation
    # ----------------------------------------------------------------

    def subscribe(
        self,
        asset_type: str,
        symbol: str,
        callback: Optional[Callable[[TickData], None]] = None,
    ) -> int:
        """
        Subscribe to real-time data for a symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
            callback: Optional callback for tick updates

        Returns:
            Request ID
        """
        key = (asset_type, symbol)

        with self._lock:
            if key in self._subscriptions:
                log.debug(f"Already subscribed to {asset_type}/{symbol}")
                return self._subscriptions[key]

        # Get contract from asset
        contract = self._get_contract(asset_type, symbol)
        if contract is None:
            log.error(f"Could not get contract for {asset_type}/{symbol}")
            return -1

        # Initialize tick data storage
        self._tick_data[symbol] = {}

        # Subscribe via broker
        def on_tick(data: Dict[str, Any]):
            self._handle_tick(symbol, data, callback)

        req_id = self._broker.subscribe_realtime(contract, on_tick)

        with self._lock:
            self._subscriptions[key] = req_id

        log.info(f"Subscribed to {asset_type}/{symbol}: req_id={req_id}")
        return req_id

    def subscribe_contract(
        self,
        asset_type: str,
        symbol: str,
        contract: Contract,
        callback: Optional[Callable[[TickData], None]] = None,
    ) -> int:
        """
        Subscribe to real-time data for a specific contract.

        Use this for futures/options where multiple contracts exist per symbol.

        Args:
            asset_type: Type of asset
            symbol: Parent symbol (e.g., "CL")
            contract: Specific contract with local_symbol (e.g., "CLZ4")
            callback: Optional callback for tick updates

        Returns:
            Request ID
        """
        local_symbol = contract.local_symbol or symbol
        key = (asset_type, symbol, local_symbol)

        with self._lock:
            if key in self._subscriptions:
                log.debug(f"Already subscribed to {asset_type}/{symbol}/{local_symbol}")
                return self._subscriptions[key]

        # Initialize tick data storage with local_symbol
        tick_key = f"{symbol}|{local_symbol}"
        self._tick_data[tick_key] = {"local_symbol": local_symbol}

        # Subscribe via broker with specific contract
        def on_tick(data: Dict[str, Any]):
            self._handle_contract_tick(symbol, local_symbol, data, callback)

        req_id = self._broker.subscribe_realtime(contract, on_tick)

        with self._lock:
            self._subscriptions[key] = req_id

        log.info(f"Subscribed to {asset_type}/{symbol}/{local_symbol}: req_id={req_id}")
        return req_id

    def unsubscribe_contract(
        self, asset_type: str, symbol: str, local_symbol: str
    ) -> None:
        """
        Unsubscribe from real-time data for a specific contract.

        Args:
            asset_type: Type of asset
            symbol: Parent symbol
            local_symbol: Contract local symbol
        """
        key = (asset_type, symbol, local_symbol)

        with self._lock:
            if key not in self._subscriptions:
                log.debug(f"Not subscribed to {asset_type}/{symbol}/{local_symbol}")
                return

            req_id = self._subscriptions.pop(key)

        # Create a temporary contract to unsubscribe
        from src.domain.entities.contract import FutureContract
        contract = FutureContract.create(symbol=symbol, local_symbol=local_symbol)
        self._broker.unsubscribe_realtime(contract)

        # Cleanup tick data
        tick_key = f"{symbol}|{local_symbol}"
        self._tick_data.pop(tick_key, None)

        log.info(f"Unsubscribed from {asset_type}/{symbol}/{local_symbol}")

    def unsubscribe(self, asset_type: str, symbol: str) -> None:
        """
        Unsubscribe from real-time data.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
        """
        key = (asset_type, symbol)

        with self._lock:
            if key not in self._subscriptions:
                log.debug(f"Not subscribed to {asset_type}/{symbol}")
                return

            req_id = self._subscriptions.pop(key)

        # Get contract and unsubscribe
        contract = self._get_contract(asset_type, symbol)
        if contract:
            self._broker.unsubscribe_realtime(contract)

        # Cleanup tick data
        self._tick_data.pop(symbol, None)

        log.info(f"Unsubscribed from {asset_type}/{symbol}")

    def unsubscribe_all(self) -> None:
        """Unsubscribe from all real-time data."""
        with self._lock:
            keys = list(self._subscriptions.keys())

        for asset_type, symbol in keys:
            self.unsubscribe(asset_type, symbol)

        log.info("Unsubscribed from all realtime data")

    def is_subscribed(self, asset_type: str, symbol: str) -> bool:
        """
        Check if subscribed to a symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            True if subscribed
        """
        key = (asset_type, symbol)
        with self._lock:
            return key in self._subscriptions

    # ----------------------------------------------------------------
    # Extended Methods
    # ----------------------------------------------------------------

    def get_subscriptions(self) -> List[tuple]:
        """
        Get list of active subscriptions.

        Returns:
            List of (asset_type, symbol) tuples
        """
        with self._lock:
            return list(self._subscriptions.keys())

    def get_current_tick(self, symbol: str) -> Optional[TickData]:
        """
        Get current tick data for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Current TickData or None
        """
        data = self._tick_data.get(symbol)
        if not data:
            return None

        return TickData(
            symbol=symbol,
            local_symbol=data.get("local_symbol", ""),
            bid=data.get("bid", 0.0),
            bid_size=data.get("bid_size", 0),
            ask=data.get("ask", 0.0),
            ask_size=data.get("ask_size", 0),
            last=data.get("last", 0.0),
            last_size=data.get("last_size", 0),
            volume=data.get("volume", 0),
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            halted=data.get("halted", 0),
            option_historical_vol=data.get("option_historical_vol", 0.0),
            option_implied_vol=data.get("option_implied_vol", 0.0),
        )

    def subscribe_option(
        self,
        contract: Contract,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> int:
        """
        Subscribe to option real-time data.

        Args:
            contract: Option contract
            callback: Optional callback for tick updates

        Returns:
            Request ID
        """
        return self._broker.subscribe_option_realtime(contract, callback)

    # ----------------------------------------------------------------
    # Internal Methods
    # ----------------------------------------------------------------

    def _get_contract(self, asset_type: str, symbol: str) -> Optional[Contract]:
        """Get contract for a symbol."""
        if self._asset_service is None:
            log.warning("Asset service not configured")
            return None

        asset = self._asset_service.get_asset(asset_type, symbol)
        if asset is None or not asset.contract_details:
            log.warning(f"No contract details for {asset_type}/{symbol}")
            return None

        # For stocks, use first contract
        # For futures, use first active contract
        if asset.asset_type == AssetType.STOCK:
            return asset.contract_details[0].contract
        elif asset.asset_type == AssetType.FUTURE:
            # Sort by expiry and get first active
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            for cd in sorted(
                asset.contract_details,
                key=lambda x: x.contract.last_trade_date or "",
            ):
                try:
                    expiry = datetime.strptime(
                        cd.contract.last_trade_date, "%Y%m%d"
                    ).replace(tzinfo=timezone.utc)
                    if expiry > now:
                        return cd.contract
                except ValueError:
                    continue

            # Fallback to first
            return asset.contract_details[0].contract

        return asset.contract_details[0].contract

    def _handle_tick(
        self,
        symbol: str,
        data: Dict[str, Any],
        callback: Optional[Callable[[TickData], None]],
    ) -> None:
        """Handle incoming tick data."""
        if not data:
            return

        tick_type = data.get("tick_type", "")
        value = data.get("value")
        local_symbol = data.get("local_symbol", "")

        # Update accumulated tick data
        if symbol not in self._tick_data:
            self._tick_data[symbol] = {"local_symbol": local_symbol}

        # Map tick type to field
        field_map = {
            "bid": "bid",
            "ask": "ask",
            "last": "last",
            "bid_size": "bid_size",
            "ask_size": "ask_size",
            "last_size": "last_size",
            "high": "high",
            "low": "low",
            "open": "open",
            "close": "close",
            "volume": "volume",
            "halted": "halted",
            # Option volatility (generic ticks 104, 106)
            "optionhistoricalvol": "option_historical_vol",
            "option_historical_vol": "option_historical_vol",
            "optionimpliedvol": "option_implied_vol",
            "option_implied_vol": "option_implied_vol",
        }

        field = field_map.get(tick_type)
        if field:
            self._tick_data[symbol][field] = value

        # Get current full tick data
        tick_data = self.get_current_tick(symbol)
        if tick_data:
            # Post to bridge for thread-safe UI update
            self._bridge.post_tick(tick_data)

            # Call user callback
            if callback:
                callback(tick_data)

    def _handle_contract_tick(
        self,
        symbol: str,
        local_symbol: str,
        data: Dict[str, Any],
        callback: Optional[Callable[[TickData], None]],
    ) -> None:
        """Handle incoming tick data for a specific contract."""
        if not data:
            return

        tick_type = data.get("tick_type", "")
        value = data.get("value")

        # Use composite key for tick data storage
        tick_key = f"{symbol}|{local_symbol}"

        # Update accumulated tick data
        if tick_key not in self._tick_data:
            self._tick_data[tick_key] = {"local_symbol": local_symbol}

        # Map tick type to field
        field_map = {
            "bid": "bid",
            "ask": "ask",
            "last": "last",
            "bid_size": "bid_size",
            "ask_size": "ask_size",
            "last_size": "last_size",
            "high": "high",
            "low": "low",
            "open": "open",
            "close": "close",
            "volume": "volume",
            "halted": "halted",
            "optionhistoricalvol": "option_historical_vol",
            "option_historical_vol": "option_historical_vol",
            "optionimpliedvol": "option_implied_vol",
            "option_implied_vol": "option_implied_vol",
        }

        field = field_map.get(tick_type)
        if field:
            self._tick_data[tick_key][field] = value

        # Get current full tick data for this contract
        tick_data = self._get_current_contract_tick(symbol, local_symbol)
        if tick_data:
            # Post to bridge for thread-safe UI update
            self._bridge.post_tick(tick_data)

            # Call user callback
            if callback:
                callback(tick_data)

    def _get_current_contract_tick(
        self, symbol: str, local_symbol: str
    ) -> Optional[TickData]:
        """Get current tick data for a specific contract."""
        tick_key = f"{symbol}|{local_symbol}"
        data = self._tick_data.get(tick_key)
        if not data:
            return None

        return TickData(
            symbol=symbol,
            local_symbol=local_symbol,
            bid=data.get("bid", 0.0),
            bid_size=data.get("bid_size", 0),
            ask=data.get("ask", 0.0),
            ask_size=data.get("ask_size", 0),
            last=data.get("last", 0.0),
            last_size=data.get("last_size", 0),
            volume=data.get("volume", 0),
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            halted=data.get("halted", 0),
            option_historical_vol=data.get("option_historical_vol", 0.0),
            option_implied_vol=data.get("option_implied_vol", 0.0),
        )
