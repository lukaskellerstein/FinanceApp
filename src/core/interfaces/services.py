"""
Business service interfaces.

All services use callback-based async patterns for broker operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class IAssetService(ABC):
    """
    Interface for asset business operations.
    Implemented by AssetService in application layer.
    """

    @abstractmethod
    def get_asset(self, asset_type: str, symbol: str) -> Optional[Any]:
        """
        Get an asset by type and symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            Asset object or None
        """
        pass

    @abstractmethod
    def get_all_assets(self, asset_type: str) -> List[Any]:
        """
        Get all assets of a given type.

        Args:
            asset_type: Type of asset

        Returns:
            List of Asset objects
        """
        pass

    @abstractmethod
    def save_asset(self, asset: Any) -> None:
        """
        Save or update an asset.

        Args:
            asset: Asset object to save
        """
        pass

    @abstractmethod
    def delete_asset(self, asset_type: str, symbol: str) -> None:
        """
        Delete an asset.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
        """
        pass

    @abstractmethod
    def exists(self, asset_type: str, symbol: str) -> bool:
        """
        Check if an asset exists.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            True if asset exists
        """
        pass

    @abstractmethod
    def fetch_contract_details(
        self,
        asset_type: str,
        contract: Any,
        callback: Optional[Callable[[List[Any]], None]] = None,
    ) -> int:
        """
        Fetch contract details from broker.

        Args:
            asset_type: Type of asset
            contract: Contract object
            callback: Called with list of ContractDetails

        Returns:
            Request ID
        """
        pass


class IWatchlistService(ABC):
    """
    Interface for watchlist business operations.
    Implemented by WatchlistService in application layer.

    Supports both legacy single-watchlist and multi-watchlist operations.
    """

    # ----------------------------------------------------------------
    # Legacy methods (operate on active watchlist)
    # ----------------------------------------------------------------

    @abstractmethod
    def get_watchlist(self, asset_type: str) -> List[str]:
        """
        Get symbols in the active watchlist.

        Args:
            asset_type: Type of asset (determines watchlist)

        Returns:
            List of symbols
        """
        pass

    @abstractmethod
    def add_to_watchlist(self, asset_type: str, symbol: str) -> None:
        """
        Add a symbol to active watchlist.

        Args:
            asset_type: Type of asset
            symbol: Symbol to add
        """
        pass

    @abstractmethod
    def remove_from_watchlist(self, asset_type: str, symbol: str) -> None:
        """
        Remove a symbol from active watchlist.

        Args:
            asset_type: Type of asset
            symbol: Symbol to remove
        """
        pass

    @abstractmethod
    def update_watchlist(self, asset_type: str, symbols: List[str]) -> None:
        """
        Replace entire active watchlist with new symbols.

        Args:
            asset_type: Type of asset
            symbols: New list of symbols
        """
        pass

    # ----------------------------------------------------------------
    # Multi-watchlist methods
    # ----------------------------------------------------------------

    @abstractmethod
    def get_all_watchlists(self, asset_type: str) -> List[Dict[str, Any]]:
        """
        Get all watchlists for an asset type.

        Args:
            asset_type: Type of asset

        Returns:
            List of watchlist dictionaries with id, name, symbols
        """
        pass

    @abstractmethod
    def get_watchlist_by_id(
        self, asset_type: str, watchlist_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific watchlist by ID.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID

        Returns:
            Watchlist dictionary or None
        """
        pass

    @abstractmethod
    def create_watchlist(
        self, asset_type: str, name: str, symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new watchlist.

        Args:
            asset_type: Type of asset
            name: Display name for the watchlist
            symbols: Initial symbols (optional)

        Returns:
            Created watchlist dictionary
        """
        pass

    @abstractmethod
    def delete_watchlist(self, asset_type: str, watchlist_id: str) -> bool:
        """
        Delete a watchlist by ID.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def rename_watchlist(
        self, asset_type: str, watchlist_id: str, new_name: str
    ) -> bool:
        """
        Rename a watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID
            new_name: New display name

        Returns:
            True if renamed, False if not found
        """
        pass

    @abstractmethod
    def add_symbol_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """
        Add a symbol to a specific watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID
            symbol: Symbol to add

        Returns:
            True if added, False otherwise
        """
        pass

    @abstractmethod
    def remove_symbol_from_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """
        Remove a symbol from a specific watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID
            symbol: Symbol to remove

        Returns:
            True if removed, False otherwise
        """
        pass

    @abstractmethod
    def add_symbols_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbols: List[str]
    ) -> int:
        """
        Add multiple symbols to a watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Unique watchlist ID
            symbols: Symbols to add

        Returns:
            Number of symbols added
        """
        pass

    @abstractmethod
    def get_active_watchlist_id(self, asset_type: str) -> Optional[str]:
        """
        Get the ID of the active watchlist.

        Args:
            asset_type: Type of asset

        Returns:
            Active watchlist ID or None
        """
        pass

    @abstractmethod
    def set_active_watchlist_id(
        self, asset_type: str, watchlist_id: str
    ) -> bool:
        """
        Set the active watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Watchlist ID to set as active

        Returns:
            True if set, False if watchlist not found
        """
        pass


class IHistoricalDataService(ABC):
    """
    Interface for historical data business operations.
    Implemented by HistoricalDataService in application layer.
    """

    @abstractmethod
    def get_historical_data(self, symbol: str, timeframe: str) -> Optional[Any]:
        """
        Get historical data for a symbol from database.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., "1 day")

        Returns:
            DataFrame or None
        """
        pass

    @abstractmethod
    def download_historical_data(
        self,
        assets: List[Any],
        timeframe: str,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Any:
        """
        Download historical data for assets (full download).

        Args:
            assets: List of Asset objects
            timeframe: Timeframe
            progress_callback: Called with progress (0-100)

        Returns:
            Progress signal emitter
        """
        pass

    @abstractmethod
    def update_historical_data(
        self,
        assets: List[Any],
        timeframe: str,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> Any:
        """
        Update historical data (download only new data).

        Args:
            assets: List of Asset objects
            timeframe: Timeframe
            progress_callback: Called with progress (0-100)

        Returns:
            Progress signal emitter
        """
        pass

    @abstractmethod
    def delete_historical_data(self, symbol: str, timeframe: str) -> None:
        """
        Delete historical data for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        """
        pass

    @abstractmethod
    def delete_historical_data_matching(self, pattern: str, timeframe: str) -> int:
        """
        Delete historical data matching a pattern.

        For futures, this deletes the base symbol and all contracts.
        E.g., pattern "CL" deletes "CL", "CLZ4-20241120", "CLF5-20250120", etc.

        Args:
            pattern: Pattern to match (base symbol)
            timeframe: Timeframe

        Returns:
            Number of items deleted
        """
        pass


class IRealtimeService(ABC):
    """
    Interface for real-time data streaming.
    Implemented by RealtimeService in application layer.
    """

    @abstractmethod
    def subscribe(
        self,
        asset_type: str,
        symbol: str,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> int:
        """
        Subscribe to real-time data for a symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
            callback: Called with TickData on each update

        Returns:
            Request ID
        """
        pass

    @abstractmethod
    def unsubscribe(self, asset_type: str, symbol: str) -> None:
        """
        Unsubscribe from real-time data.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol
        """
        pass

    @abstractmethod
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all real-time data."""
        pass

    @abstractmethod
    def is_subscribed(self, asset_type: str, symbol: str) -> bool:
        """
        Check if subscribed to a symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            True if subscribed
        """
        pass
