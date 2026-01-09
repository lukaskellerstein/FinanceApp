"""
Application services with dependency injection.
"""

from src.application.services.asset_service import AssetService
from src.application.services.watchlist_service import WatchlistService
from src.application.services.historical_data_service import HistoricalDataService
from src.application.services.realtime_service import RealtimeService

__all__ = [
    "AssetService",
    "WatchlistService",
    "HistoricalDataService",
    "RealtimeService",
]
