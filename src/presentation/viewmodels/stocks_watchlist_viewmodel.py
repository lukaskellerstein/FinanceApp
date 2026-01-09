"""
ViewModel for Stocks Watchlist page.

Manages multiple stocks watchlists with tabs.
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import pyqtSignal

from src.application.bootstrap import get_app
from src.core.interfaces.services import (
    IWatchlistService,
    IRealtimeService,
    IAssetService,
)
from src.core.interfaces.broker import IBrokerClient
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.contract import StockContract
from src.domain.value_objects.tick_data import TickData
from src.presentation.core.base_view_model import BaseViewModel, ObservableProperty
from src.presentation.core.command import Command
from src.presentation.state.market_data_bridge import MarketDataBridge

log = logging.getLogger("CellarLogger")


class StocksWatchlistViewModel(BaseViewModel):
    """
    ViewModel for Stocks Watchlist page with multi-watchlist support.

    Manages:
    - Multiple watchlists with tabs
    - Real-time data subscriptions per active watchlist
    - Watchlist CRUD operations

    Example:
        vm = StocksWatchlistViewModel(
            watchlist_service=watchlist_service,
            realtime_service=realtime_service,
            market_data_bridge=bridge,
        )
        vm.load_all_watchlists()
        vm.create_watchlist("Tech Stocks")
    """

    # Signals for UI updates
    tick_updated = pyqtSignal(str, object)  # symbol, tick_data dict
    symbol_added = pyqtSignal(str)
    symbol_removed = pyqtSignal(str)
    symbols_added = pyqtSignal(list)  # list of symbols

    # Multi-watchlist signals
    watchlists_loaded = pyqtSignal(list)  # list of watchlist dicts
    watchlist_created = pyqtSignal(dict)  # new watchlist dict
    watchlist_deleted = pyqtSignal(str)  # watchlist_id
    watchlist_switched = pyqtSignal(str)  # watchlist_id
    active_watchlist_loaded = pyqtSignal(list)  # symbols in active watchlist

    # Asset creation signals (for adding tickers not in Assets collection)
    contracts_received = pyqtSignal(str, list)  # symbol, list of ContractDetails
    asset_created = pyqtSignal(str)  # symbol
    asset_creation_error = pyqtSignal(str, str)  # symbol, error message
    asset_creation_started = pyqtSignal(str)  # symbol (for showing loading status)

    # Observable properties
    watchlists = ObservableProperty[List[Dict[str, Any]]]([])
    active_watchlist_id = ObservableProperty[str]("")
    active_watchlist_name = ObservableProperty[str]("")
    symbols = ObservableProperty[List[str]]([])
    selected_symbol = ObservableProperty[str]("")
    selected_asset = ObservableProperty[Optional[Asset]](None)

    def __init__(
        self,
        watchlist_service: IWatchlistService,
        realtime_service: IRealtimeService,
        asset_service: IAssetService,
        market_data_bridge: MarketDataBridge,
    ):
        """
        Initialize ViewModel.

        Args:
            watchlist_service: Service for watchlist operations
            realtime_service: Service for real-time data
            asset_service: Service for asset lookup
            market_data_bridge: Bridge for thread-safe tick updates
        """
        super().__init__()

        self._watchlist_service = watchlist_service
        self._realtime_service = realtime_service
        self._asset_service = asset_service
        self._bridge = market_data_bridge

        # Track subscriptions for current watchlist
        self._subscriptions: Dict[str, int] = {}  # symbol -> req_id

        # Commands
        self.add_symbol_command = Command(
            execute=self._add_symbol,
            can_execute=lambda: bool(self.active_watchlist_id),
        )
        self.remove_symbol_command = Command(
            execute=self._remove_symbol,
            can_execute=lambda: bool(self.selected_symbol),
        )
        self.refresh_command = Command(
            execute=self._refresh_active_watchlist,
            can_execute=lambda: not self.is_busy,
        )

        # Connect to market data bridge
        self._bridge.tick_received.connect(self._on_tick_received)

        log.info("StocksWatchlistViewModel initialized")

    # ----------------------------------------------------------------
    # Multi-watchlist operations
    # ----------------------------------------------------------------

    def load_all_watchlists(self) -> None:
        """Load all watchlists and set the active one."""
        self.is_busy = True

        try:
            # Get all watchlists
            watchlists = self._watchlist_service.get_all_watchlists("STOCK")
            self.watchlists = watchlists

            # Get active watchlist ID
            active_id = self._watchlist_service.get_active_watchlist_id("STOCK")

            # If no active, use first watchlist
            if not active_id and watchlists:
                active_id = watchlists[0]["id"]
                self._watchlist_service.set_active_watchlist_id("STOCK", active_id)

            if active_id:
                self.active_watchlist_id = active_id
                # Find name for active watchlist
                for wl in watchlists:
                    if wl["id"] == active_id:
                        self.active_watchlist_name = wl.get("name", "")
                        break

            self.watchlists_loaded.emit(watchlists)
            log.info(f"Loaded {len(watchlists)} watchlists")

            # Load symbols for active watchlist
            if active_id:
                self._load_watchlist_symbols(active_id)

        except Exception as e:
            self.handle_error(e)
        finally:
            self.is_busy = False

    def switch_watchlist(self, watchlist_id: str) -> None:
        """
        Switch to a different watchlist.

        Args:
            watchlist_id: ID of watchlist to switch to
        """
        if watchlist_id == self.active_watchlist_id:
            return

        try:
            # Unsubscribe from current watchlist
            self._unsubscribe_all()

            # Update active watchlist
            self._watchlist_service.set_active_watchlist_id("STOCK", watchlist_id)
            self.active_watchlist_id = watchlist_id

            # Find name
            for wl in self.watchlists:
                if wl["id"] == watchlist_id:
                    self.active_watchlist_name = wl.get("name", "")
                    break

            # Load symbols for new watchlist
            self._load_watchlist_symbols(watchlist_id)

            self.watchlist_switched.emit(watchlist_id)
            log.info(f"Switched to watchlist {watchlist_id}")

        except Exception as e:
            self.handle_error(e)

    def create_watchlist(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Create a new watchlist.

        Args:
            name: Display name for the watchlist

        Returns:
            Created watchlist dict or None on error
        """
        try:
            new_watchlist = self._watchlist_service.create_watchlist("STOCK", name)

            # Update local list
            current = list(self.watchlists)
            current.append(new_watchlist)
            self.watchlists = current

            self.watchlist_created.emit(new_watchlist)
            log.info(f"Created watchlist '{name}'")

            return new_watchlist

        except Exception as e:
            self.handle_error(e)
            return None

    def delete_watchlist(self, watchlist_id: str) -> bool:
        """
        Delete a watchlist.

        Args:
            watchlist_id: ID of watchlist to delete

        Returns:
            True if deleted
        """
        try:
            # Don't allow deleting last watchlist
            if len(self.watchlists) <= 1:
                log.warning("Cannot delete the last watchlist")
                return False

            # Unsubscribe if deleting active watchlist
            if watchlist_id == self.active_watchlist_id:
                self._unsubscribe_all()

            result = self._watchlist_service.delete_watchlist("STOCK", watchlist_id)

            if result:
                # Update local list
                current = [wl for wl in self.watchlists if wl["id"] != watchlist_id]
                self.watchlists = current

                # Switch to another watchlist if we deleted the active one
                if watchlist_id == self.active_watchlist_id and current:
                    self.switch_watchlist(current[0]["id"])

                self.watchlist_deleted.emit(watchlist_id)
                log.info(f"Deleted watchlist {watchlist_id}")

            return result

        except Exception as e:
            self.handle_error(e)
            return False

    def rename_watchlist(self, watchlist_id: str, new_name: str) -> bool:
        """
        Rename a watchlist.

        Args:
            watchlist_id: ID of watchlist to rename
            new_name: New display name

        Returns:
            True if renamed
        """
        try:
            result = self._watchlist_service.rename_watchlist(
                "STOCK", watchlist_id, new_name
            )

            if result:
                # Update local list
                for wl in self.watchlists:
                    if wl["id"] == watchlist_id:
                        wl["name"] = new_name
                        break

                if watchlist_id == self.active_watchlist_id:
                    self.active_watchlist_name = new_name

                # Trigger property change
                self.watchlists = list(self.watchlists)
                log.info(f"Renamed watchlist to '{new_name}'")

            return result

        except Exception as e:
            self.handle_error(e)
            return False

    def get_all_saved_assets(self) -> List[Asset]:
        """Get all saved stock assets for selection dialog."""
        return self._watchlist_service.get_all_saved_assets("STOCK")

    def get_existing_watchlist_names(self) -> List[str]:
        """Get list of existing watchlist names for validation."""
        return [wl.get("name", "") for wl in self.watchlists]

    # ----------------------------------------------------------------
    # Asset creation (for symbols not in Assets collection)
    # ----------------------------------------------------------------

    def asset_exists(self, symbol: str) -> bool:
        """
        Check if an asset exists in the Assets collection.

        Args:
            symbol: Symbol to check

        Returns:
            True if asset exists
        """
        return self._asset_service.exists("STOCK", symbol)

    def is_broker_connected(self) -> bool:
        """Check if broker is connected for fetching contract details."""
        try:
            app = get_app()
            if not app.container.is_registered(IBrokerClient):
                return False
            broker = app.container.resolve(IBrokerClient)
            return broker.is_connected()
        except Exception:
            return False

    def fetch_and_create_asset(self, symbol: str) -> None:
        """
        Fetch contract details from IB and create asset.

        If multiple contracts match, emits contracts_received signal
        for UI to show selection dialog.

        Args:
            symbol: Symbol to search for in IB
        """
        if not self.is_broker_connected():
            self.asset_creation_error.emit(
                symbol, "Not connected to IB - click Connect first"
            )
            return

        self.asset_creation_started.emit(symbol)

        # Create contract for search (empty exchange to get all matches)
        contract = StockContract.create(
            symbol=symbol, exchange="", primary_exchange=""
        )

        # Store reference for callback
        vm_ref = self

        def on_details_received(details_list):
            if not details_list:
                vm_ref.asset_creation_error.emit(
                    symbol, f"No contract found for {symbol}"
                )
                return

            # If multiple contracts match, let UI choose
            if len(details_list) > 1:
                vm_ref.contracts_received.emit(symbol, details_list)
                return

            # Single match - save directly and add to watchlist
            vm_ref._create_asset_and_add_to_watchlist(symbol, details_list[0])

        self._asset_service.fetch_contract_details(
            "STOCK", contract, callback=on_details_received
        )

    def create_asset_from_selection(self, symbol: str, selected_cd) -> None:
        """
        Create asset from user-selected contract details.

        Called by UI after user selects from multiple contracts.

        Args:
            symbol: The symbol
            selected_cd: Selected ContractDetails object
        """
        self._create_asset_and_add_to_watchlist(symbol, selected_cd)

    def _create_asset_and_add_to_watchlist(self, symbol: str, contract_details) -> None:
        """
        Create asset from contract details and add to watchlist.

        Args:
            symbol: The symbol
            contract_details: ContractDetails to save
        """
        try:
            asset = Asset(
                symbol=symbol,
                asset_type=AssetType.STOCK,
                contract_details=[contract_details],
            )
            self._asset_service.save_asset(asset)
            self.asset_created.emit(symbol)
            log.info(f"Created asset {symbol} from IB contract")

            # Now add to watchlist
            self._add_symbol(symbol)

        except Exception as e:
            self.asset_creation_error.emit(symbol, str(e))
            log.error(f"Error creating asset {symbol}: {e}")

    # ----------------------------------------------------------------
    # Symbol operations (on active watchlist)
    # ----------------------------------------------------------------

    def _load_watchlist_symbols(self, watchlist_id: str) -> None:
        """Load symbols for a specific watchlist."""
        watchlist = self._watchlist_service.get_watchlist_by_id("STOCK", watchlist_id)

        if watchlist:
            symbols = watchlist.get("symbols", [])
            self.symbols = symbols

            # Subscribe to real-time for each symbol
            for symbol in symbols:
                self._subscribe_realtime(symbol)

            self.active_watchlist_loaded.emit(symbols)
            log.debug(f"Loaded {len(symbols)} symbols for watchlist")

    def _refresh_active_watchlist(self) -> None:
        """Refresh the active watchlist."""
        if self.active_watchlist_id:
            self._unsubscribe_all()
            self._load_watchlist_symbols(self.active_watchlist_id)

    def add_symbol(self, symbol: str) -> None:
        """Add a single symbol to the active watchlist."""
        self._add_symbol(symbol)

    def _add_symbol(self, symbol: str = None) -> None:
        """Internal add symbol implementation."""
        if not symbol or not self.active_watchlist_id:
            return

        symbol = symbol.upper().strip()
        if not symbol:
            return

        if symbol in self.symbols:
            log.debug(f"Symbol {symbol} already in watchlist")
            return

        try:
            result = self._watchlist_service.add_symbol_to_watchlist(
                "STOCK", self.active_watchlist_id, symbol
            )

            if result:
                # Update local list
                current = list(self.symbols)
                current.append(symbol)
                self.symbols = current

                # Subscribe to real-time
                self._subscribe_realtime(symbol)

                self.symbol_added.emit(symbol)
                log.info(f"Added {symbol} to active watchlist")

        except Exception as e:
            self.handle_error(e)

    def add_symbols(self, symbols: List[str]) -> int:
        """
        Add multiple symbols to the active watchlist.

        Args:
            symbols: List of symbols to add

        Returns:
            Number of symbols added
        """
        if not self.active_watchlist_id:
            return 0

        try:
            count = self._watchlist_service.add_symbols_to_watchlist(
                "STOCK", self.active_watchlist_id, symbols
            )

            if count > 0:
                # Reload symbols
                self._load_watchlist_symbols(self.active_watchlist_id)
                self.symbols_added.emit(symbols)
                log.info(f"Added {count} symbols to active watchlist")

            return count

        except Exception as e:
            self.handle_error(e)
            return 0

    def remove_symbol(self, symbol: str) -> None:
        """Remove a symbol from the active watchlist."""
        self._remove_symbol(symbol)

    def _remove_symbol(self, symbol: str = None) -> None:
        """Internal remove symbol implementation."""
        if not symbol:
            symbol = self.selected_symbol

        if not symbol or symbol not in self.symbols or not self.active_watchlist_id:
            return

        try:
            # Unsubscribe from real-time
            self._unsubscribe_realtime(symbol)

            result = self._watchlist_service.remove_symbol_from_watchlist(
                "STOCK", self.active_watchlist_id, symbol
            )

            if result:
                # Update local list
                current = list(self.symbols)
                current.remove(symbol)
                self.symbols = current

                self.symbol_removed.emit(symbol)
                log.info(f"Removed {symbol} from active watchlist")

        except Exception as e:
            self.handle_error(e)

    def select_symbol(self, symbol: str) -> None:
        """
        Select a symbol and load its asset details.

        Args:
            symbol: Symbol to select
        """
        self.selected_symbol = symbol

        if symbol:
            asset = self._asset_service.get_asset("STOCK", symbol)
            self.selected_asset = asset

    def get_asset(self, symbol: str) -> Optional[Asset]:
        """Get asset for a symbol."""
        return self._asset_service.get_asset("STOCK", symbol)

    # ----------------------------------------------------------------
    # Legacy methods (operate on active watchlist) - backward compatibility
    # ----------------------------------------------------------------

    def load_watchlist(self) -> None:
        """Load watchlists (legacy method - now calls load_all_watchlists)."""
        self.load_all_watchlists()

    def update_watchlist_order(self, symbols: List[str]) -> None:
        """Update the watchlist symbol order."""
        if not self.active_watchlist_id:
            return

        try:
            # Get current watchlist and update symbols
            watchlist = self._watchlist_service.get_watchlist_by_id(
                "STOCK", self.active_watchlist_id
            )
            if watchlist:
                # Use the service's update for the active watchlist
                self._watchlist_service.update_watchlist("STOCK", symbols)
                self.symbols = symbols
                log.info("Watchlist order updated")
        except Exception as e:
            self.handle_error(e)

    # ----------------------------------------------------------------
    # Real-time data
    # ----------------------------------------------------------------

    def _subscribe_realtime(self, symbol: str) -> None:
        """Subscribe to real-time data for a symbol."""
        if symbol in self._subscriptions:
            return

        def on_tick(tick: TickData):
            self.tick_updated.emit(symbol, tick.to_dict())

        req_id = self._realtime_service.subscribe("STOCK", symbol, on_tick)
        self._subscriptions[symbol] = req_id
        log.debug(f"Subscribed to {symbol}: req_id={req_id}")

    def _unsubscribe_realtime(self, symbol: str) -> None:
        """Unsubscribe from real-time data."""
        if symbol not in self._subscriptions:
            return

        self._realtime_service.unsubscribe("STOCK", symbol)
        del self._subscriptions[symbol]
        log.debug(f"Unsubscribed from {symbol}")

    def _unsubscribe_all(self) -> None:
        """Unsubscribe from all real-time data."""
        for symbol in list(self._subscriptions.keys()):
            self._unsubscribe_realtime(symbol)

    def _on_tick_received(self, tick_data: TickData) -> None:
        """Handle tick data from bridge."""
        symbol = tick_data.symbol
        if symbol in self._subscriptions:
            self.tick_updated.emit(symbol, tick_data.to_dict())

    def dispose(self) -> None:
        """Clean up subscriptions."""
        self._unsubscribe_all()

        try:
            self._bridge.tick_received.disconnect(self._on_tick_received)
        except (TypeError, RuntimeError):
            pass

        super().dispose()
        log.info("StocksWatchlistViewModel disposed")
