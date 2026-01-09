"""
Bar data value object for OHLCV historical data.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Tuple


@dataclass
class BarData:
    """
    Immutable OHLCV bar data for historical data.

    Represents a single candlestick/bar with open, high, low, close, volume.
    """

    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def to_tuple(self) -> Tuple[datetime, float, float, float, float, int]:
        """Convert to tuple for compatibility with existing code."""
        return (self.datetime, self.open, self.high, self.low, self.close, self.volume)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "datetime": self.datetime.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }

    @classmethod
    def from_tuple(
        cls, data: Tuple[datetime, float, float, float, float, int]
    ) -> BarData:
        """Create from tuple."""
        return cls(
            datetime=data[0],
            open=data[1],
            high=data[2],
            low=data[3],
            close=data[4],
            volume=data[5],
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BarData:
        """Create from dictionary."""
        dt = data.get("datetime")
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        return cls(
            datetime=dt,
            open=data.get("open", 0.0),
            high=data.get("high", 0.0),
            low=data.get("low", 0.0),
            close=data.get("close", 0.0),
            volume=data.get("volume", 0),
        )

    @property
    def body_size(self) -> float:
        """Calculate the body size (open to close difference)."""
        return abs(self.close - self.open)

    @property
    def range_size(self) -> float:
        """Calculate the range (high to low difference)."""
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        """Check if bar is bullish (close > open)."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """Check if bar is bearish (close < open)."""
        return self.close < self.open


def bars_from_tuples(
    data: List[Tuple[datetime, float, float, float, float, int]]
) -> List[BarData]:
    """
    Convert list of tuples to list of BarData.

    Args:
        data: List of (datetime, open, high, low, close, volume) tuples

    Returns:
        List of BarData objects
    """
    return [BarData.from_tuple(t) for t in data]


def bars_to_tuples(
    bars: List[BarData],
) -> List[Tuple[datetime, float, float, float, float, int]]:
    """
    Convert list of BarData to list of tuples.

    Args:
        bars: List of BarData objects

    Returns:
        List of (datetime, open, high, low, close, volume) tuples
    """
    return [b.to_tuple() for b in bars]
