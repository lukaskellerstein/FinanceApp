"""
Interface definitions for dependency injection.
"""

from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.repositories import (
    IAssetRepository,
    IHistoricalDataRepository,
    IWatchlistRepository,
)
from src.core.interfaces.services import (
    IAssetService,
    IWatchlistService,
    IHistoricalDataService,
    IRealtimeService,
)

__all__ = [
    "IBrokerClient",
    "IAssetRepository",
    "IHistoricalDataRepository",
    "IWatchlistRepository",
    "IAssetService",
    "IWatchlistService",
    "IHistoricalDataService",
    "IRealtimeService",
]
