"""
Presentation components - Reusable UI widgets.

These components are designed for use within the presentation layer
and follow PyQt6 patterns.
"""

from src.presentation.components.create_watchlist_dialog import CreateWatchlistDialog
from src.presentation.components.asset_selection_dialog import AssetSelectionDialog
from src.presentation.components.watchlist_tab_widget import WatchlistTabWidget

__all__ = [
    "CreateWatchlistDialog",
    "AssetSelectionDialog",
    "WatchlistTabWidget",
]
