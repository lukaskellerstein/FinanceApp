"""
State management for the presentation layer.
"""

from src.presentation.state.store import AppStore, StateSlice, AssetState
from src.presentation.state.market_data_bridge import MarketDataBridge, MarketDataMessage

__all__ = [
    "AppStore",
    "StateSlice",
    "AssetState",
    "MarketDataBridge",
    "MarketDataMessage",
]
