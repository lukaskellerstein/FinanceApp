"""
Watchlist service implementation.

Provides business logic for watchlist management with dependency injection.
Supports multiple named watchlists per asset type.
"""

import logging
from typing import Any, Dict, List, Optional

from src.core.interfaces.repositories import IWatchlistRepository
from src.core.interfaces.services import IWatchlistService, IAssetService
from src.domain.entities.asset import Asset, AssetType

log = logging.getLogger("CellarLogger")


class WatchlistService(IWatchlistService):
    """
    Watchlist service with dependency injection.

    Provides:
    - Multi-watchlist CRUD operations
    - Asset lookup for watchlist symbols
    - Legacy single-watchlist compatibility

    Example:
        service = WatchlistService(
            watchlist_repository=FileWatchlistRepository("/path"),
            asset_service=asset_service,
        )
        watchlists = service.get_all_watchlists("STOCK")
    """

    def __init__(
        self,
        watchlist_repository: IWatchlistRepository,
        asset_service: Optional[IAssetService] = None,
    ):
        """
        Initialize service.

        Args:
            watchlist_repository: Repository for watchlist persistence
            asset_service: Optional asset service for asset lookup
        """
        self._repository = watchlist_repository
        self._asset_service = asset_service
        log.info("WatchlistService initialized")

    # ----------------------------------------------------------------
    # Legacy single-watchlist methods (backward compatibility)
    # These operate on the active watchlist
    # ----------------------------------------------------------------

    def get_watchlist(self, asset_type: str) -> List[str]:
        """
        Get symbols in the active watchlist.

        Args:
            asset_type: Type of asset (determines watchlist name)

        Returns:
            List of symbols
        """
        watchlist_name = self._get_watchlist_name(asset_type)
        return self._repository.get(watchlist_name)

    def add_to_watchlist(self, asset_type: str, symbol: str) -> None:
        """
        Add a symbol to active watchlist.

        Args:
            asset_type: Type of asset
            symbol: Symbol to add
        """
        watchlist_name = self._get_watchlist_name(asset_type)
        self._repository.add_symbol(watchlist_name, symbol)
        log.info(f"Added {symbol} to {asset_type} watchlist")

    def remove_from_watchlist(self, asset_type: str, symbol: str) -> None:
        """
        Remove a symbol from active watchlist.

        Args:
            asset_type: Type of asset
            symbol: Symbol to remove
        """
        watchlist_name = self._get_watchlist_name(asset_type)
        self._repository.remove_symbol(watchlist_name, symbol)
        log.info(f"Removed {symbol} from {asset_type} watchlist")

    def update_watchlist(self, asset_type: str, symbols: List[str]) -> None:
        """
        Replace entire active watchlist with new symbols.

        Args:
            asset_type: Type of asset
            symbols: New list of symbols
        """
        watchlist_name = self._get_watchlist_name(asset_type)
        self._repository.update(watchlist_name, symbols)
        log.info(f"Updated {asset_type} watchlist with {len(symbols)} symbols")

    # ----------------------------------------------------------------
    # Multi-watchlist methods
    # ----------------------------------------------------------------

    def get_all_watchlists(self, asset_type: str) -> List[Dict[str, Any]]:
        """Get all watchlists for an asset type."""
        watchlist_name = self._get_watchlist_name(asset_type)
        return self._repository.get_all_watchlists(watchlist_name)

    def get_watchlist_by_id(
        self, asset_type: str, watchlist_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific watchlist by ID."""
        watchlist_name = self._get_watchlist_name(asset_type)
        return self._repository.get_watchlist_by_id(watchlist_name, watchlist_id)

    def create_watchlist(
        self, asset_type: str, name: str, symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.create_watchlist(watchlist_name, name, symbols)
        log.info(f"Created watchlist '{name}' for {asset_type}")
        return result

    def delete_watchlist(self, asset_type: str, watchlist_id: str) -> bool:
        """Delete a watchlist by ID."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.delete_watchlist(watchlist_name, watchlist_id)
        if result:
            log.info(f"Deleted watchlist {watchlist_id} for {asset_type}")
        return result

    def rename_watchlist(
        self, asset_type: str, watchlist_id: str, new_name: str
    ) -> bool:
        """Rename a watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.rename_watchlist(
            watchlist_name, watchlist_id, new_name
        )
        if result:
            log.info(f"Renamed watchlist {watchlist_id} to '{new_name}'")
        return result

    def add_symbol_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """Add a symbol to a specific watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.add_symbol_to_watchlist(
            watchlist_name, watchlist_id, symbol
        )
        if result:
            log.info(f"Added {symbol} to watchlist {watchlist_id}")
        return result

    def remove_symbol_from_watchlist(
        self, asset_type: str, watchlist_id: str, symbol: str
    ) -> bool:
        """Remove a symbol from a specific watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.remove_symbol_from_watchlist(
            watchlist_name, watchlist_id, symbol
        )
        if result:
            log.info(f"Removed {symbol} from watchlist {watchlist_id}")
        return result

    def add_symbols_to_watchlist(
        self, asset_type: str, watchlist_id: str, symbols: List[str]
    ) -> int:
        """Add multiple symbols to a watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        count = self._repository.add_symbols_to_watchlist(
            watchlist_name, watchlist_id, symbols
        )
        log.info(f"Added {count} symbols to watchlist {watchlist_id}")
        return count

    def get_active_watchlist_id(self, asset_type: str) -> Optional[str]:
        """Get the ID of the active watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        return self._repository.get_active_watchlist_id(watchlist_name)

    def set_active_watchlist_id(
        self, asset_type: str, watchlist_id: str
    ) -> bool:
        """Set the active watchlist."""
        watchlist_name = self._get_watchlist_name(asset_type)
        result = self._repository.set_active_watchlist_id(
            watchlist_name, watchlist_id
        )
        if result:
            log.info(f"Set active watchlist to {watchlist_id}")
        return result

    # ----------------------------------------------------------------
    # Extended Methods
    # ----------------------------------------------------------------

    def get_asset(self, asset_type: str, symbol: str) -> Optional[Asset]:
        """
        Get asset details for a watchlist symbol.

        Args:
            asset_type: Type of asset
            symbol: Asset symbol

        Returns:
            Asset object or None
        """
        if self._asset_service is None:
            log.warning("Asset service not configured")
            return None

        return self._asset_service.get_asset(asset_type, symbol)

    def get_watchlist_with_assets(self, asset_type: str) -> List[Asset]:
        """
        Get all assets in the active watchlist.

        Args:
            asset_type: Type of asset

        Returns:
            List of Asset objects (only those found in asset repository)
        """
        if self._asset_service is None:
            log.warning("Asset service not configured")
            return []

        symbols = self.get_watchlist(asset_type)
        assets = []

        for symbol in symbols:
            asset = self._asset_service.get_asset(asset_type, symbol)
            if asset:
                assets.append(asset)

        return assets

    def get_watchlist_with_assets_by_id(
        self, asset_type: str, watchlist_id: str
    ) -> List[Asset]:
        """
        Get all assets in a specific watchlist.

        Args:
            asset_type: Type of asset
            watchlist_id: Watchlist ID

        Returns:
            List of Asset objects
        """
        if self._asset_service is None:
            log.warning("Asset service not configured")
            return []

        watchlist = self.get_watchlist_by_id(asset_type, watchlist_id)
        if not watchlist:
            return []

        assets = []
        for symbol in watchlist.get("symbols", []):
            asset = self._asset_service.get_asset(asset_type, symbol)
            if asset:
                assets.append(asset)

        return assets

    def get_all_saved_assets(self, asset_type: str) -> List[Asset]:
        """
        Get all saved assets of a type (for asset selection dialog).

        Args:
            asset_type: Type of asset

        Returns:
            List of all saved Asset objects
        """
        if self._asset_service is None:
            log.warning("Asset service not configured")
            return []

        return self._asset_service.get_all_assets(asset_type)

    def watchlist_exists(self, asset_type: str) -> bool:
        """
        Check if any watchlists exist for asset type.

        Args:
            asset_type: Type of asset

        Returns:
            True if watchlists exist
        """
        watchlist_name = self._get_watchlist_name(asset_type)
        return self._repository.exists(watchlist_name)

    def list_all_watchlists(self) -> List[str]:
        """
        List all available watchlist names (asset types with watchlists).

        Returns:
            List of watchlist names
        """
        return self._repository.list_watchlists()

    # ----------------------------------------------------------------
    # Helper Methods
    # ----------------------------------------------------------------

    def _get_watchlist_name(self, asset_type: str) -> str:
        """
        Convert asset type to watchlist name.

        Args:
            asset_type: Asset type string

        Returns:
            Watchlist name (lowercase for file storage)
        """
        # Map asset type to watchlist file name (lowercase)
        type_map = {
            "STOCK": "stock",
            "FUTURE": "future",
            "OPTION": "option",
            "INDEX": "index",
            "FOREX": "forex",
            "CRYPTO": "crypto",
        }
        return type_map.get(asset_type.upper(), asset_type.lower())
