"""
Market Data Bridge - Thread-safe communication between IB client and UI.

Solves the thread-safety problem where IB client callbacks run in a
separate thread but need to update Qt UI components which must be
updated from the main thread.
"""

from __future__ import annotations
from dataclasses import dataclass
from queue import Queue
from typing import Any, Optional
import time
import logging

from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from src.presentation.state.store import AppStore, AssetState
from src.domain.value_objects.tick_data import TickData

log = logging.getLogger("CellarLogger")


@dataclass
class MarketDataMessage:
    """
    Message from IB thread to main thread.

    Encapsulates a single piece of market data update that needs
    to be processed in the Qt main thread.
    """

    msg_type: str  # 'tick', 'error', 'connection', 'historical'
    asset_type: str  # 'STOCK', 'FUTURE', 'OPTION'
    symbol: str
    local_symbol: str
    field: str
    value: Any
    timestamp: float


class MarketDataBridge(QObject):
    """
    Bridge between IB client thread and Qt main thread.

    Uses a thread-safe queue for communication:
    1. IB callbacks enqueue messages (can be called from any thread)
    2. QTimer processes queue in Qt main thread
    3. Updates AppStore and emits signals

    This replaces the direct RxPy observable emissions which were
    not thread-safe with Qt.

    Example:
        bridge = MarketDataBridge()
        bridge.start()

        # In IB client callback (any thread):
        bridge.enqueue_tick("STOCK", "AAPL", "AAPL", "last", 150.50, time.time())

        # Connect to signals in UI:
        bridge.tick_received.connect(self.on_tick)
    """

    # Signals for UI updates (emitted in main thread)
    tick_received = pyqtSignal(str, str, str, object)  # asset_type, symbol, field, value
    connection_changed = pyqtSignal(bool)
    error_occurred = pyqtSignal(int, str)  # error_code, message

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._message_queue: Queue[MarketDataMessage] = Queue()
        self._store = AppStore.get_instance()
        self._running = False

        # Timer to process queue in Qt event loop
        self._process_timer = QTimer(self)
        self._process_timer.timeout.connect(self._process_queue)

        # Statistics
        self._messages_processed = 0
        self._messages_dropped = 0

    def start(self, interval_ms: int = 10) -> None:
        """
        Start processing messages.

        Args:
            interval_ms: Timer interval in milliseconds (default 10ms)
        """
        if self._running:
            return

        self._running = True
        self._process_timer.start(interval_ms)
        log.info(f"MarketDataBridge started with {interval_ms}ms interval")

    def stop(self) -> None:
        """Stop processing messages."""
        self._running = False
        self._process_timer.stop()
        log.info(
            f"MarketDataBridge stopped. "
            f"Processed: {self._messages_processed}, "
            f"Dropped: {self._messages_dropped}"
        )

    @property
    def is_running(self) -> bool:
        """Check if bridge is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._message_queue.qsize()

    def enqueue_tick(
        self,
        asset_type: str,
        symbol: str,
        local_symbol: str,
        field: str,
        value: Any,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Enqueue a tick update.

        Thread-safe - can be called from any thread (IB callback thread).

        Args:
            asset_type: Type of asset ("STOCK", "FUTURE", etc.)
            symbol: Asset symbol
            local_symbol: Local symbol (for futures)
            field: Field name (bid, ask, last, volume, etc.)
            value: Field value
            timestamp: Update timestamp (defaults to current time)
        """
        if not self._running:
            self._messages_dropped += 1
            return

        msg = MarketDataMessage(
            msg_type="tick",
            asset_type=asset_type,
            symbol=symbol,
            local_symbol=local_symbol,
            field=field,
            value=value,
            timestamp=timestamp or time.time(),
        )
        self._message_queue.put(msg)

    def enqueue_error(self, error_code: int, message: str) -> None:
        """
        Enqueue an error message.

        Args:
            error_code: IB error code
            message: Error message
        """
        if not self._running:
            return

        msg = MarketDataMessage(
            msg_type="error",
            asset_type="",
            symbol="",
            local_symbol="",
            field="error",
            value={"code": error_code, "message": message},
            timestamp=time.time(),
        )
        self._message_queue.put(msg)

    def enqueue_connection_status(self, is_connected: bool) -> None:
        """
        Enqueue a connection status change.

        Args:
            is_connected: Whether connected to broker
        """
        msg = MarketDataMessage(
            msg_type="connection",
            asset_type="",
            symbol="",
            local_symbol="",
            field="status",
            value=is_connected,
            timestamp=time.time(),
        )
        self._message_queue.put(msg)

    def post_tick_update(
        self,
        symbol: str,
        local_symbol: str,
        tick_type: str,
        value: Any,
        asset_type: str = "STOCK",
    ) -> None:
        """
        Post a single tick field update.

        Convenience method for IBClient to post tick updates without
        needing to know the asset type (defaults to STOCK).

        Args:
            symbol: Asset symbol
            local_symbol: Local symbol (for futures contracts)
            tick_type: IB tick type name (e.g., "bid", "ask", "last")
            value: Tick value
            asset_type: Asset type (default "STOCK")
        """
        # Map IB tick type names to TickData field names
        # IB sends lowercase names like "bid", "ask", "last" etc.
        # Tick type 104 = optionHistoricalVol, 106 = optionImpliedVol
        field_map = {
            "bid": "bid",
            "bid_price": "bid",
            "ask": "ask",
            "ask_price": "ask",
            "last": "last",
            "last_price": "last",
            "bid_size": "bid_size",
            "bidsize": "bid_size",
            "ask_size": "ask_size",
            "asksize": "ask_size",
            "last_size": "last_size",
            "lastsize": "last_size",
            "volume": "volume",
            "high": "high",
            "low": "low",
            "open": "open",
            "close": "close",
            "halted": "halted",
            # Option volatility tick types (generic ticks 104, 106)
            "optionhistoricalvol": "option_historical_vol",
            "option_historical_vol": "option_historical_vol",
            "optionimpliedvol": "option_implied_vol",
            "option_implied_vol": "option_implied_vol",
        }

        field = field_map.get(tick_type.lower(), tick_type.lower())
        self.enqueue_tick(asset_type, symbol, local_symbol, field, value)

    def post_tick(self, tick_data: TickData) -> None:
        """
        Post a complete TickData update.

        Enqueues all non-zero fields from the TickData object.

        Args:
            tick_data: Complete tick data object
        """
        # Determine asset type from local_symbol (futures have different local symbols)
        asset_type = "FUTURE" if tick_data.local_symbol and tick_data.local_symbol != tick_data.symbol else "STOCK"

        # Post all relevant fields
        if tick_data.bid > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "bid", tick_data.bid)
        if tick_data.ask > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "ask", tick_data.ask)
        if tick_data.last > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "last", tick_data.last)
        if tick_data.volume > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "volume", tick_data.volume)
        if tick_data.high > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "high", tick_data.high)
        if tick_data.low > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "low", tick_data.low)
        if tick_data.open > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "open", tick_data.open)
        if tick_data.close > 0:
            self.enqueue_tick(asset_type, tick_data.symbol, tick_data.local_symbol, "close", tick_data.close)

    def _process_queue(self) -> None:
        """
        Process pending messages from the queue.

        Runs in Qt main thread via QTimer.
        Processes up to 100 messages per tick to avoid blocking UI.
        """
        processed = 0
        max_per_tick = 100

        while not self._message_queue.empty() and processed < max_per_tick:
            try:
                msg = self._message_queue.get_nowait()
                self._handle_message(msg)
                processed += 1
                self._messages_processed += 1
            except Exception as e:
                log.error(f"Error processing message: {e}")

    def _handle_message(self, msg: MarketDataMessage) -> None:
        """
        Handle a single message and update store.

        Args:
            msg: The message to handle
        """
        if msg.msg_type == "tick":
            self._handle_tick(msg)
        elif msg.msg_type == "error":
            self._handle_error(msg)
        elif msg.msg_type == "connection":
            self._handle_connection(msg)

    def _handle_tick(self, msg: MarketDataMessage) -> None:
        """Handle a tick message and update the store."""
        try:
            slice_store = self._store.get_asset_slice(msg.asset_type)
        except ValueError:
            log.warning(f"Unknown asset type: {msg.asset_type}")
            return

        key = f"{msg.symbol}|{msg.local_symbol}"

        def updater(current: Optional[AssetState]) -> AssetState:
            if current is None:
                tick_data = TickData(
                    symbol=msg.symbol,
                    local_symbol=msg.local_symbol,
                )
                current = AssetState(tick_data=tick_data, is_subscribed=True)

            # Update the specific field
            new_tick_data = current.tick_data.with_update(msg.field, msg.value)
            return AssetState(
                tick_data=new_tick_data,
                is_subscribed=current.is_subscribed,
                last_updated=msg.timestamp,
            )

        slice_store.update(key, updater)

        # Emit signal for components that prefer signals over store subscription
        self.tick_received.emit(
            msg.asset_type,
            msg.symbol,
            msg.field,
            msg.value,
        )

    def _handle_error(self, msg: MarketDataMessage) -> None:
        """Handle an error message."""
        error_data = msg.value
        code = error_data.get("code", 0)
        message = error_data.get("message", "Unknown error")
        self.error_occurred.emit(code, message)

    def _handle_connection(self, msg: MarketDataMessage) -> None:
        """Handle a connection status change."""
        is_connected = msg.value
        self._store.is_connected = is_connected
        self.connection_changed.emit(is_connected)
