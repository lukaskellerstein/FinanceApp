"""
Tick data value object for real-time market data.

Replaces the 17+ BehaviorSubject pattern in RealtimeDataItem.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import time


@dataclass
class TickData:
    """
    Immutable tick data structure for real-time market data.

    Consolidates all tick fields into a single object instead of
    17+ separate BehaviorSubjects, reducing memory overhead and
    simplifying state management.

    Example:
        tick = TickData(symbol="AAPL", local_symbol="AAPL")
        updated = tick.with_update("last", 150.50)
    """

    symbol: str
    local_symbol: str
    bid: float = 0.0
    bid_size: int = 0
    ask: float = 0.0
    ask_size: int = 0
    last: float = 0.0
    last_size: int = 0
    volume: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    halted: int = 0
    option_historical_vol: float = 0.0  # IB tick type 104
    option_implied_vol: float = 0.0     # IB tick type 106
    timestamp: float = field(default_factory=time.time)

    def with_update(self, field_name: str, value: Any) -> TickData:
        """
        Return a new TickData with one field updated.

        This maintains immutability - the original object is not modified.

        Args:
            field_name: Name of the field to update
            value: New value for the field

        Returns:
            New TickData instance with the updated field
        """
        if not hasattr(self, field_name):
            return self

        data = {
            "symbol": self.symbol,
            "local_symbol": self.local_symbol,
            "bid": self.bid,
            "bid_size": self.bid_size,
            "ask": self.ask,
            "ask_size": self.ask_size,
            "last": self.last,
            "last_size": self.last_size,
            "volume": self.volume,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "halted": self.halted,
            "option_historical_vol": self.option_historical_vol,
            "option_implied_vol": self.option_implied_vol,
            "timestamp": time.time(),  # Always update timestamp
        }
        data[field_name] = value
        return TickData(**data)

    def with_updates(self, updates: Dict[str, Any]) -> TickData:
        """
        Return a new TickData with multiple fields updated.

        Args:
            updates: Dictionary of field names to new values

        Returns:
            New TickData instance with the updated fields
        """
        data = {
            "symbol": self.symbol,
            "local_symbol": self.local_symbol,
            "bid": self.bid,
            "bid_size": self.bid_size,
            "ask": self.ask,
            "ask_size": self.ask_size,
            "last": self.last,
            "last_size": self.last_size,
            "volume": self.volume,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "halted": self.halted,
            "option_historical_vol": self.option_historical_vol,
            "option_implied_vol": self.option_implied_vol,
            "timestamp": time.time(),
        }
        for field_name, value in updates.items():
            if field_name in data:
                data[field_name] = value
        return TickData(**data)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for serialization.

        Returns:
            Dictionary representation of the tick data
        """
        return {
            "symbol": self.symbol,
            "local_symbol": self.local_symbol,
            "bid": self.bid,
            "bid_size": self.bid_size,
            "ask": self.ask,
            "ask_size": self.ask_size,
            "last": self.last,
            "last_size": self.last_size,
            "volume": self.volume,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "halted": self.halted,
            "option_historical_vol": self.option_historical_vol,
            "option_implied_vol": self.option_implied_vol,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TickData:
        """
        Create from dictionary.

        Args:
            data: Dictionary with tick data fields

        Returns:
            New TickData instance
        """
        return cls(
            symbol=data.get("symbol", ""),
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
            timestamp=data.get("timestamp", time.time()),
        )

    @property
    def change(self) -> float:
        """Calculate price change from close to last."""
        if self.close > 0 and self.last > 0:
            return ((self.last - self.close) / self.close) * 100
        return 0.0

    @property
    def change_value(self) -> float:
        """Calculate absolute price change from close to last."""
        return self.last - self.close

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread."""
        return self.ask - self.bid

    @property
    def key(self) -> str:
        """Get the unique key for this tick data."""
        return f"{self.symbol}|{self.local_symbol}"
