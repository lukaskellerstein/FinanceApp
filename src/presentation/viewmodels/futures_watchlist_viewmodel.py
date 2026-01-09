"""
ViewModel for Futures Watchlist page.

Manages multiple futures watchlists with tabs.
"""

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import pyqtSignal

from src.application.bootstrap import get_app
from src.core.interfaces.services import (
    IWatchlistService,
    IRealtimeService,
    IAssetService,
    IHistoricalDataService,
)
from src.core.interfaces.broker import IBrokerClient
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.contract import Contract, FutureContract
from src.domain.value_objects.tick_data import TickData
from src.presentation.core.base_view_model import BaseViewModel, ObservableProperty
from src.presentation.core.command import Command
from src.presentation.state.market_data_bridge import MarketDataBridge

log = logging.getLogger("CellarLogger")


class FuturesWatchlistViewModel(BaseViewModel):
    """
    ViewModel for Futures Watchlist page with multi-watchlist support.

    Manages:
    - Multiple watchlists with tabs
    - Real-time data subscriptions for active contracts
    - Watchlist CRUD operations

    Futures are more complex than stocks as each symbol can have
    multiple contracts with different expiration dates.

    Example:
        vm = FuturesWatchlistViewModel(
            watchlist_service=watchlist_service,
            realtime_service=realtime_service,
            asset_service=asset_service,
            market_data_bridge=bridge,
        )
        vm.load_all_watchlists()
        vm.create_watchlist("Energy")
    """

    # Signals
    tick_updated = pyqtSignal(str, str, object)  # symbol, local_symbol, tick_data
    symbol_added = pyqtSignal(str)
    symbol_removed = pyqtSignal(str)
    symbols_added = pyqtSignal(list)  # list of symbols
    contracts_loaded = pyqtSignal(str, list)  # symbol, list of contracts

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

    # Asset deletion signals
    asset_deleted = pyqtSignal(str, int)  # symbol, count of historical data items deleted

    # Observable properties
    watchlists = ObservableProperty[List[Dict[str, Any]]]([])
    active_watchlist_id = ObservableProperty[str]("")
    active_watchlist_name = ObservableProperty[str]("")
    symbols = ObservableProperty[List[str]]([])
    selected_symbol = ObservableProperty[str]("")
    selected_asset = ObservableProperty[Optional[Asset]](None)
    assets = ObservableProperty[Dict[str, Asset]]({})

    # Allowed exchanges for futures
    ALLOWED_EXCHANGES = ["GLOBEX", "ECBOT", "NYMEX", "NYBOT"]

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

        # Track subscriptions: (symbol, local_symbol) -> req_id
        self._subscriptions: Dict[tuple, int] = {}

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

        # Note: Futures use direct callback from RealtimeService.subscribe_contract,
        # not the bridge signal. The bridge signal has different signature and is
        # used for the AppStore pattern. We don't connect to it here.

        log.info("FuturesWatchlistViewModel initialized")

    # ----------------------------------------------------------------
    # Multi-watchlist operations
    # ----------------------------------------------------------------

    def load_all_watchlists(self) -> None:
        """Load all watchlists and set the active one."""
        self.is_busy = True

        try:
            # Get all watchlists
            watchlists = self._watchlist_service.get_all_watchlists("FUTURE")
            self.watchlists = watchlists

            # Get active watchlist ID
            active_id = self._watchlist_service.get_active_watchlist_id("FUTURE")

            # If no active, use first watchlist
            if not active_id and watchlists:
                active_id = watchlists[0]["id"]
                self._watchlist_service.set_active_watchlist_id("FUTURE", active_id)

            if active_id:
                self.active_watchlist_id = active_id
                # Find name for active watchlist
                for wl in watchlists:
                    if wl["id"] == active_id:
                        self.active_watchlist_name = wl.get("name", "")
                        break

            self.watchlists_loaded.emit(watchlists)
            log.info(f"Loaded {len(watchlists)} futures watchlists")

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
            self._watchlist_service.set_active_watchlist_id("FUTURE", watchlist_id)
            self.active_watchlist_id = watchlist_id

            # Find name
            for wl in self.watchlists:
                if wl["id"] == watchlist_id:
                    self.active_watchlist_name = wl.get("name", "")
                    break

            # Load symbols for new watchlist
            self._load_watchlist_symbols(watchlist_id)

            self.watchlist_switched.emit(watchlist_id)
            log.info(f"Switched to futures watchlist {watchlist_id}")

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
            new_watchlist = self._watchlist_service.create_watchlist("FUTURE", name)

            # Update local list
            current = list(self.watchlists)
            current.append(new_watchlist)
            self.watchlists = current

            self.watchlist_created.emit(new_watchlist)
            log.info(f"Created futures watchlist '{name}'")

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

            result = self._watchlist_service.delete_watchlist("FUTURE", watchlist_id)

            if result:
                # Update local list
                current = [wl for wl in self.watchlists if wl["id"] != watchlist_id]
                self.watchlists = current

                # Switch to another watchlist if we deleted the active one
                if watchlist_id == self.active_watchlist_id and current:
                    self.switch_watchlist(current[0]["id"])

                self.watchlist_deleted.emit(watchlist_id)
                log.info(f"Deleted futures watchlist {watchlist_id}")

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
                "FUTURE", watchlist_id, new_name
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
                log.info(f"Renamed futures watchlist to '{new_name}'")

            return result

        except Exception as e:
            self.handle_error(e)
            return False

    def get_all_saved_assets(self) -> List[Asset]:
        """Get all saved futures assets for selection dialog."""
        return self._watchlist_service.get_all_saved_assets("FUTURE")

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
        return self._asset_service.exists("FUTURE", symbol)

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

        For futures, tries multiple exchanges to find contracts.
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

        # For futures, try multiple exchanges
        exchanges_to_try = list(self.ALLOWED_EXCHANGES) + [""]
        all_details = []
        exchanges_tried = [0]  # Use list to allow mutation in closure
        vm_ref = self

        def try_next_exchange():
            if exchanges_tried[0] >= len(exchanges_to_try):
                # All exchanges tried, process results
                if not all_details:
                    vm_ref.asset_creation_error.emit(
                        symbol, f"No contract found for {symbol}"
                    )
                    return

                if len(all_details) > 1:
                    vm_ref.contracts_received.emit(symbol, all_details)
                else:
                    vm_ref._create_asset_and_add_to_watchlist(symbol, all_details[0])
                return

            exchange = exchanges_to_try[exchanges_tried[0]]
            exchanges_tried[0] += 1
            # Important: leave local_symbol empty for search
            contract = FutureContract.create(
                symbol=symbol, exchange=exchange, local_symbol=""
            )

            def on_details_received(details_list):
                if details_list:
                    all_details.extend(details_list)
                try_next_exchange()

            vm_ref._asset_service.fetch_contract_details(
                "FUTURE", contract, callback=on_details_received
            )

        try_next_exchange()

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
                asset_type=AssetType.FUTURE,
                contract_details=[contract_details],
            )
            self._asset_service.save_asset(asset)
            self.asset_created.emit(symbol)
            log.info(f"Created futures asset {symbol} from IB contract")

            # Now add to watchlist
            self._add_symbol(symbol)

        except Exception as e:
            self.asset_creation_error.emit(symbol, str(e))
            log.error(f"Error creating futures asset {symbol}: {e}")

    # ----------------------------------------------------------------
    # Symbol operations (on active watchlist)
    # ----------------------------------------------------------------

    def _load_watchlist_symbols(self, watchlist_id: str) -> None:
        """Load symbols for a specific watchlist."""
        watchlist = self._watchlist_service.get_watchlist_by_id("FUTURE", watchlist_id)

        if watchlist:
            symbols = watchlist.get("symbols", [])
            self.symbols = symbols

            # Load assets and subscribe to real-time for each
            assets_dict = {}
            for symbol in symbols:
                asset = self._asset_service.get_asset("FUTURE", symbol)
                if asset:
                    assets_dict[symbol] = asset
                    self._subscribe_contracts(asset)

            self.assets = assets_dict
            self.active_watchlist_loaded.emit(symbols)
            log.debug(f"Loaded {len(symbols)} futures symbols for watchlist")

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
            log.debug(f"Symbol {symbol} already in futures watchlist")
            return

        try:
            result = self._watchlist_service.add_symbol_to_watchlist(
                "FUTURE", self.active_watchlist_id, symbol
            )

            if result:
                # Update local list
                current = list(self.symbols)
                current.append(symbol)
                self.symbols = current

                # Load asset and subscribe
                asset = self._asset_service.get_asset("FUTURE", symbol)
                if asset:
                    assets = dict(self.assets)
                    assets[symbol] = asset
                    self.assets = assets
                    self._subscribe_contracts(asset)

                self.symbol_added.emit(symbol)
                log.info(f"Added {symbol} to active futures watchlist")

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
                "FUTURE", self.active_watchlist_id, symbols
            )

            if count > 0:
                # Reload symbols
                self._load_watchlist_symbols(self.active_watchlist_id)
                self.symbols_added.emit(symbols)
                log.info(f"Added {count} symbols to active futures watchlist")

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
            # Unsubscribe all contracts
            asset = self.assets.get(symbol)
            if asset:
                for cd in asset.contract_details:
                    self._unsubscribe_realtime(symbol, cd.contract.local_symbol)

            result = self._watchlist_service.remove_symbol_from_watchlist(
                "FUTURE", self.active_watchlist_id, symbol
            )

            if result:
                # Update local lists
                current = list(self.symbols)
                current.remove(symbol)
                self.symbols = current

                assets = dict(self.assets)
                assets.pop(symbol, None)
                self.assets = assets

                self.symbol_removed.emit(symbol)
                log.info(f"Removed {symbol} from active futures watchlist")

        except Exception as e:
            self.handle_error(e)

    def delete_symbol_with_data(self, symbol: str) -> None:
        """
        Delete a symbol completely including all data.

        This removes:
        1. All historical data for the base symbol and all subcontracts
        2. The asset JSON file
        3. The symbol from the watchlist

        Args:
            symbol: Symbol to delete
        """
        if not symbol:
            return

        try:
            app = get_app()

            # Get asset to find all contracts
            asset = self.assets.get(symbol) or self._asset_service.get_asset(
                "FUTURE", symbol
            )

            # 1. Unsubscribe from real-time data first
            if asset:
                for cd in asset.contract_details:
                    self._unsubscribe_realtime(symbol, cd.contract.local_symbol)

            # 2. Delete historical data for all contracts matching this symbol
            # The pattern matching will find: CL, CLZ4-20241120, CLF5-20250120, etc.
            deleted_count = 0
            try:
                historical_service = app.historical_data_service
                # Delete matching data for common timeframes
                for timeframe in ["1 day", "1 hour", "5 mins"]:
                    count = historical_service.delete_historical_data_matching(
                        symbol, timeframe
                    )
                    deleted_count += count
                log.info(
                    f"Deleted {deleted_count} historical data items for {symbol}"
                )
            except Exception as e:
                log.warning(f"Error deleting historical data for {symbol}: {e}")

            # 3. Delete the asset JSON file
            try:
                self._asset_service.delete_asset("FUTURE", symbol)
                log.info(f"Deleted asset file for {symbol}")
            except Exception as e:
                log.warning(f"Error deleting asset file for {symbol}: {e}")

            # 4. Remove from watchlist (same as _remove_symbol)
            if symbol in self.symbols and self.active_watchlist_id:
                result = self._watchlist_service.remove_symbol_from_watchlist(
                    "FUTURE", self.active_watchlist_id, symbol
                )

                if result:
                    # Update local lists
                    current = list(self.symbols)
                    if symbol in current:
                        current.remove(symbol)
                    self.symbols = current

                    assets = dict(self.assets)
                    assets.pop(symbol, None)
                    self.assets = assets

            self.symbol_removed.emit(symbol)
            self.asset_deleted.emit(symbol, deleted_count)
            log.info(
                f"Deleted {symbol} completely "
                f"({deleted_count} historical data items)"
            )

        except Exception as e:
            self.handle_error(e)
            log.error(f"Error deleting {symbol} with data: {e}")

    def select_symbol(self, symbol: str) -> None:
        """Select a symbol."""
        self.selected_symbol = symbol
        self.selected_asset = self.assets.get(symbol)

    def get_asset(self, symbol: str) -> Optional[Asset]:
        """Get asset for a symbol."""
        return self.assets.get(symbol) or self._asset_service.get_asset(
            "FUTURE", symbol
        )

    def get_active_contracts(self, symbol: str) -> List[Contract]:
        """
        Get active contracts for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            List of active (non-expired) contracts
        """
        from datetime import datetime, timezone

        asset = self.assets.get(symbol)
        if not asset:
            return []

        now = datetime.now(timezone.utc)
        active = []

        for cd in asset.contract_details:
            try:
                expiry = datetime.strptime(
                    cd.contract.last_trade_date, "%Y%m%d"
                ).replace(tzinfo=timezone.utc)
                if expiry >= now:
                    active.append(cd.contract)
            except ValueError:
                continue

        return sorted(active, key=lambda c: c.last_trade_date)

    # ----------------------------------------------------------------
    # Legacy methods (backward compatibility)
    # ----------------------------------------------------------------

    def load_watchlist(self) -> None:
        """Load watchlists (legacy method - now calls load_all_watchlists)."""
        self.load_all_watchlists()

    # ----------------------------------------------------------------
    # Real-time data
    # ----------------------------------------------------------------

    def _subscribe_contracts(self, asset: Asset) -> None:
        """Subscribe to real-time for active contracts of an asset."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        log.debug(f"_subscribe_contracts: {asset.symbol} has {len(asset.contract_details)} contracts")

        for cd in asset.contract_details:
            contract = cd.contract
            log.debug(f"  Checking contract: {contract.local_symbol}, exchange={contract.exchange}, expiry={contract.last_trade_date}")

            # Filter by exchange
            if contract.exchange not in self.ALLOWED_EXCHANGES:
                log.debug(f"    Skipped - exchange {contract.exchange} not in {self.ALLOWED_EXCHANGES}")
                continue

            # Check if contract is active (not expired)
            try:
                expiry = datetime.strptime(
                    contract.last_trade_date, "%Y%m%d"
                ).replace(tzinfo=timezone.utc)
                if expiry < now:
                    log.debug(f"    Skipped - expired {expiry} < {now}")
                    continue
            except ValueError:
                log.debug(f"    Skipped - invalid date format")
                continue

            log.debug(f"    Subscribing to {contract.local_symbol}")
            self._subscribe_realtime(asset.symbol, contract)

    def _subscribe_realtime(self, symbol: str, contract: Contract) -> None:
        """Subscribe to real-time data for a specific contract."""
        key = (symbol, contract.local_symbol)
        if key in self._subscriptions:
            return

        def on_tick(tick: TickData):
            self.tick_updated.emit(symbol, contract.local_symbol, tick.to_dict())

        # Use subscribe_contract for futures to subscribe to specific contract
        req_id = self._realtime_service.subscribe_contract(
            "FUTURE", symbol, contract, on_tick
        )
        self._subscriptions[key] = req_id
        log.debug(f"Subscribed to {symbol}/{contract.local_symbol}")

    def _unsubscribe_realtime(self, symbol: str, local_symbol: str) -> None:
        """Unsubscribe from real-time data for a specific contract."""
        key = (symbol, local_symbol)
        if key not in self._subscriptions:
            return

        # Use unsubscribe_contract for futures to unsubscribe from specific contract
        self._realtime_service.unsubscribe_contract("FUTURE", symbol, local_symbol)
        del self._subscriptions[key]
        log.debug(f"Unsubscribed from {symbol}/{local_symbol}")

    def _unsubscribe_all(self) -> None:
        """Unsubscribe from all real-time data."""
        for (symbol, local_symbol) in list(self._subscriptions.keys()):
            self._unsubscribe_realtime(symbol, local_symbol)

    def dispose(self) -> None:
        """Clean up subscriptions."""
        self._unsubscribe_all()
        super().dispose()
        log.info("FuturesWatchlistViewModel disposed")
