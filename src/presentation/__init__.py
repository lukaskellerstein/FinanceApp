"""
Presentation layer - UI components using MVVM pattern.

Contains:
- core/: Base classes (BaseViewModel, BaseView, BaseWindow, Command)
- state/: Application state management (AppStore, MarketDataBridge)
- viewmodels/: ViewModels for pages
- views/: Migrated page views

Note: viewmodels and views are NOT imported here to avoid circular imports.
Import them directly from their submodules when needed.
"""

from src.presentation.core import (
    BaseViewModel,
    ObservableProperty,
    BaseView,
    BaseWindow,
    Command,
    AsyncCommand,
)
from src.presentation.state import (
    AppStore,
    StateSlice,
    AssetState,
    MarketDataBridge,
    MarketDataMessage,
)

# Note: viewmodels and views are imported lazily to avoid circular imports
# Import directly: from src.presentation.viewmodels import StocksWatchlistViewModel

__all__ = [
    # MVVM base classes
    "BaseViewModel",
    "ObservableProperty",
    "BaseView",
    "BaseWindow",
    "Command",
    "AsyncCommand",
    # State management
    "AppStore",
    "StateSlice",
    "AssetState",
    "MarketDataBridge",
    "MarketDataMessage",
]
