"""
Repository interfaces for data persistence.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime


class IAssetRepository(ABC):
    """
    Interface for asset persistence operations.
    Implemented by JsonAssetRepository in infrastructure layer.
    """

    @abstractmethod
    def get(self, asset_type: str, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get an asset by type and symbol.

        Args:
            asset_type: Type of asset (e.g., "STOCK", "FUTURE")
            symbol: Asset symbol

        Returns:
            Asset dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_all(self, asset_type: str) -> List[Dict[str, Any]]:
        """
        Get all assets of a given type.

        Args:
            asset_type: Type of asset

        Returns:
            List of asset dictionaries
        """
        pass

    @abstractmethod
    def save(self, asset: Dict[str, Any]) -> None:
        """
        Save or update an asset.

        Args:
            asset: Asset dictionary to save
        """
        pass

    @abstractmethod
    def delete(self, asset_type: str, symbol: str) -> None:
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


class IHistoricalDataRepository(ABC):
    """
    Interface for historical data persistence.
    Implemented by PyStoreRepository in infrastructure layer.
    """

    @abstractmethod
    def get(self, symbol: str, timeframe: str) -> Optional[Any]:
        """
        Get historical data for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., "1 day")

        Returns:
            DataFrame or None if not found
        """
        pass

    @abstractmethod
    def save(self, symbol: str, timeframe: str, data: Any) -> None:
        """
        Save historical data (overwrite).

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data: Data to save (DataFrame or list of tuples)
        """
        pass

    @abstractmethod
    def append(self, symbol: str, timeframe: str, data: Any) -> None:
        """
        Append historical data to existing data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data: Data to append
        """
        pass

    @abstractmethod
    def delete(self, symbol: str, timeframe: str) -> None:
        """
        Delete historical data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        """
        pass

    @abstractmethod
    def get_last_date(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Get the last date of stored data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            Last datetime or None if no data
        """
        pass

    @abstractmethod
    def exists(self, symbol: str, timeframe: str) -> bool:
        """
        Check if data exists for symbol/timeframe.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            True if data exists
        """
        pass

    @abstractmethod
    def get_symbols_matching(self, pattern: str, timeframe: str) -> List[str]:
        """
        Get all symbols matching a pattern for a timeframe.

        Args:
            pattern: Pattern to match (e.g., "CL" matches "CL", "CLZ4-20241120", etc.)
            timeframe: Timeframe

        Returns:
            List of matching symbols
        """
        pass

    @abstractmethod
    def delete_matching(self, pattern: str, timeframe: str) -> int:
        """
        Delete all historical data matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "CL" to delete all CL contracts)
            timeframe: Timeframe

        Returns:
            Number of items deleted
        """
        pass


class IWatchlistRepository(ABC):
    """
    Interface for watchlist persistence.
    Implemented by FileWatchlistRepository in infrastructure layer.

    Supports both legacy single-watchlist operations and multi-watchlist operations.
    """

    # ----------------------------------------------------------------
    # Legacy single-watchlist methods (for backward compatibility)
    # ----------------------------------------------------------------

    @abstractmethod
    def get(self, watchlist_name: str) -> List[str]:
        """
        Get symbols in a watchlist.

        Args:
            watchlist_name: Name of the watchlist

        Returns:
            List of symbols
        """
        pass

    @abstractmethod
    def add_symbol(self, watchlist_name: str, symbol: str) -> None:
        """
        Add a symbol to a watchlist.

        Args:
            watchlist_name: Name of the watchlist
            symbol: Symbol to add
        """
        pass

    @abstractmethod
    def remove_symbol(self, watchlist_name: str, symbol: str) -> None:
        """
        Remove a symbol from a watchlist.

        Args:
            watchlist_name: Name of the watchlist
            symbol: Symbol to remove
        """
        pass

    @abstractmethod
    def update(self, watchlist_name: str, symbols: List[str]) -> None:
        """
        Replace entire watchlist with new symbols.

        Args:
            watchlist_name: Name of the watchlist
            symbols: New list of symbols
        """
        pass

    @abstractmethod
    def exists(self, watchlist_name: str) -> bool:
        """
        Check if watchlist exists.

        Args:
            watchlist_name: Name of the watchlist

        Returns:
            True if watchlist exists
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
            asset_type: Type of asset (e.g., "stock", "future")

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
            Watchlist dictionary or None if not found
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
            Created watchlist dictionary with id
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
            True if added, False if watchlist not found or symbol exists
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
            True if removed, False if watchlist not found or symbol not in list
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
            Number of symbols actually added (excludes duplicates)
        """
        pass

    @abstractmethod
    def get_active_watchlist_id(self, asset_type: str) -> Optional[str]:
        """
        Get the ID of the active/selected watchlist.

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
        Set the active/selected watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Watchlist ID to set as active

        Returns:
            True if set, False if watchlist not found
        """
        pass
