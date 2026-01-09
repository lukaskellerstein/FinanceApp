"""
Historical data service implementation.

Provides business logic for historical data download/update with DI.
"""

import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd
from PyQt6.QtCore import QObject, pyqtSignal

from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.repositories import IHistoricalDataRepository
from src.core.interfaces.services import IHistoricalDataService
from src.domain.entities.asset import Asset, AssetType
from src.domain.entities.contract import Contract
from src.domain.entities.timeframe import TimeFrame
from src.domain.value_objects.bar_data import BarData
from src.application.helpers.time_blocks import get_time_blocks

log = logging.getLogger("CellarLogger")


class DownloadProgress(QObject):
    """Qt signal emitter for download progress."""

    progress_changed = pyqtSignal(float)  # 0-100
    completed = pyqtSignal()
    error = pyqtSignal(str)


class HistoricalDataService(IHistoricalDataService):
    """
    Historical data service with dependency injection.

    Provides:
    - Historical data retrieval from database
    - Download historical data from broker
    - Update existing data with new bars

    Example:
        service = HistoricalDataService(
            historical_repository=pystore_repo,
            broker_client=ib_client,
        )
        df = service.get_historical_data("AAPL", "1 day")
    """

    # Default start date for full downloads
    # Changed from 1986 to 2000 to reduce timeout blocks for newer stocks
    # IB doesn't respond for date ranges with no data, causing 60s timeouts
    DEFAULT_START_DATE = datetime(2000, 1, 1, tzinfo=timezone.utc)

    # Timeout for each historical data request (reduced from 60s)
    # IB should respond within 15s if there's data; no response = no data
    DOWNLOAD_TIMEOUT = 15

    def __init__(
        self,
        historical_repository: IHistoricalDataRepository,
        broker_client: Optional[IBrokerClient] = None,
    ):
        """
        Initialize service.

        Args:
            historical_repository: Repository for historical data
            broker_client: Optional broker client for downloads
        """
        self._repository = historical_repository
        self._broker = broker_client
        self._current_task: Optional[threading.Thread] = None
        self._running = False
        log.info("HistoricalDataService initialized")

    # ----------------------------------------------------------------
    # IHistoricalDataService Implementation
    # ----------------------------------------------------------------

    def get_historical_data(
        self, symbol: str, timeframe: str
    ) -> Optional[pd.DataFrame]:
        """
        Get historical data for a symbol from database.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., "1 day")

        Returns:
            DataFrame with OHLCV data or None
        """
        return self._repository.get(symbol, timeframe)

    def download_historical_data(
        self,
        assets: List[Asset],
        timeframe: str,
        max_block_days: int = 365,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> DownloadProgress:
        """
        Download historical data for assets (full download).

        Clears existing data and downloads from the beginning.

        Args:
            assets: List of Asset objects
            timeframe: Timeframe string
            max_block_days: Maximum days per request block
            progress_callback: Optional callback for progress updates

        Returns:
            DownloadProgress signal emitter
        """
        progress = DownloadProgress()

        if self._broker is None:
            progress.error.emit("Broker client not configured")
            return progress

        # Build list of contracts and time blocks
        download_items = self._build_download_items(
            assets, timeframe, max_block_days, clear_existing=True
        )

        # Start background download
        self._start_download_task(
            download_items, timeframe, progress, progress_callback
        )

        return progress

    def update_historical_data(
        self,
        assets: List[Asset],
        timeframe: str,
        max_block_days: int = 365,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> DownloadProgress:
        """
        Update historical data (download only new data).

        Checks existing data and downloads from last available date.

        Args:
            assets: List of Asset objects
            timeframe: Timeframe string
            max_block_days: Maximum days per request block
            progress_callback: Optional callback for progress updates

        Returns:
            DownloadProgress signal emitter
        """
        progress = DownloadProgress()

        if self._broker is None:
            progress.error.emit("Broker client not configured")
            return progress

        # Build list of contracts and time blocks (update mode)
        download_items = self._build_update_items(
            assets, timeframe, max_block_days
        )

        if not download_items:
            log.info("No updates needed")
            progress.progress_changed.emit(100.0)
            progress.completed.emit()
            return progress

        # Start background download
        self._start_download_task(
            download_items, timeframe, progress, progress_callback
        )

        return progress

    def get_last_date(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Get the last available date for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            Last datetime or None
        """
        return self._repository.get_last_date(symbol, timeframe)

    def exists(self, symbol: str, timeframe: str) -> bool:
        """
        Check if data exists for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            True if data exists
        """
        return self._repository.exists(symbol, timeframe)

    def delete(self, symbol: str, timeframe: str) -> None:
        """
        Delete historical data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        """
        self._repository.delete(symbol, timeframe)
        log.info(f"Deleted historical data: {symbol}/{timeframe}")

    def delete_historical_data(self, symbol: str, timeframe: str) -> None:
        """
        Delete historical data for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        """
        self.delete(symbol, timeframe)

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
        return self._repository.delete_matching(pattern, timeframe)

    def cancel_download(self) -> None:
        """Cancel any running download task."""
        self._running = False
        if self._current_task and self._current_task.is_alive():
            log.info("Cancelling download task")

    # ----------------------------------------------------------------
    # Internal Methods
    # ----------------------------------------------------------------

    def _wait_for_connection(self, timeout: float = 10.0) -> bool:
        """
        Wait for broker connection to be established.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if connected, False if timeout or error
        """
        if self._broker is None:
            log.error("Broker client not configured")
            return False

        # Check if already connected
        if self._broker.is_connected():
            log.debug("Broker already connected for download")
            return True

        # Use broker's wait_for_connection method
        log.info("Waiting for broker connection...")
        result = self._broker.wait_for_connection(timeout)

        if result:
            log.info("Broker connection established for download")
        else:
            error = self._broker.connection_error
            log.error(f"Failed to connect to broker: {error or 'timeout'}")

        return result

    def _build_download_items(
        self,
        assets: List[Asset],
        timeframe: str,
        max_block_days: int,
        clear_existing: bool = False,
    ) -> List[Dict[str, Any]]:
        """Build list of download items for full download."""
        items = []
        now = datetime.now(timezone.utc)
        tf = TimeFrame.from_str(timeframe)

        for asset in assets:
            if clear_existing:
                self._clear_asset_data(asset, tf)

            if asset.asset_type == AssetType.STOCK:
                items.extend(
                    self._build_stock_items(asset, now, max_block_days)
                )
            elif asset.asset_type == AssetType.FUTURE:
                items.extend(
                    self._build_future_items(asset, now, max_block_days)
                )

        return items

    def _build_update_items(
        self,
        assets: List[Asset],
        timeframe: str,
        max_block_days: int,
    ) -> List[Dict[str, Any]]:
        """Build list of download items for update."""
        items = []
        now = datetime.now(timezone.utc)
        tf = TimeFrame.from_str(timeframe)

        for asset in assets:
            if asset.asset_type == AssetType.STOCK:
                items.extend(
                    self._build_stock_update_items(
                        asset, tf, now, max_block_days
                    )
                )
            elif asset.asset_type == AssetType.FUTURE:
                items.extend(
                    self._build_future_update_items(
                        asset, tf, now, max_block_days
                    )
                )

        return items

    def _clear_asset_data(self, asset: Asset, timeframe: TimeFrame) -> None:
        """Clear existing data for an asset."""
        try:
            if asset.asset_type == AssetType.STOCK:
                self._repository.delete(asset.symbol, timeframe.value)
            elif asset.asset_type == AssetType.FUTURE:
                for cd in asset.contract_details:
                    symbol = self._get_future_symbol(cd.contract)
                    self._repository.delete(symbol, timeframe.value)
        except Exception as e:
            log.warning(f"Error clearing data for {asset.symbol}: {e}")

    def _build_stock_items(
        self, asset: Asset, now: datetime, max_block_days: int
    ) -> List[Dict[str, Any]]:
        """Build download items for a stock."""
        log.info(f"Building stock items for {asset.symbol}")
        log.info(f"  contract_details count: {len(asset.contract_details) if asset.contract_details else 0}")

        if not asset.contract_details:
            log.warning(f"No contract details for {asset.symbol}, skipping download")
            return []

        contract = asset.contract_details[0].contract
        time_blocks = get_time_blocks(
            self.DEFAULT_START_DATE, now, max_block_days
        )

        return [
            {
                "contract": contract,
                "symbol": asset.symbol,
                "from": block[0],
                "to": block[1],
            }
            for block in time_blocks
        ]

    def _build_future_items(
        self, asset: Asset, now: datetime, max_block_days: int
    ) -> List[Dict[str, Any]]:
        """Build download items for futures."""
        items = []

        for cd in asset.contract_details:
            contract = cd.contract
            last_trade = self._parse_expiry_date(contract.last_trade_date)

            if last_trade is None:
                continue

            # Determine download range
            if last_trade > now:
                # Active contract
                start = now - timedelta(days=max_block_days)
                end = now
            elif last_trade > self.DEFAULT_START_DATE:
                # Expired contract
                start = last_trade - timedelta(days=max_block_days)
                end = last_trade
            else:
                continue

            items.append({
                "contract": contract,
                "symbol": self._get_future_symbol(contract),
                "from": start,
                "to": end,
            })

        return items

    def _build_stock_update_items(
        self,
        asset: Asset,
        timeframe: TimeFrame,
        now: datetime,
        max_block_days: int,
    ) -> List[Dict[str, Any]]:
        """Build update items for a stock."""
        if not asset.contract_details:
            log.warning(f"No contract details for {asset.symbol}")
            return []

        contract = asset.contract_details[0].contract
        last_date = self._repository.get_last_date(asset.symbol, timeframe.value)

        log.info(
            f"Update check for {asset.symbol}: last_date={last_date}, now={now}"
        )

        if last_date is None:
            # No data, do full download
            log.info(f"No existing data for {asset.symbol}, doing full download")
            return self._build_stock_items(asset, now, max_block_days)

        # Ensure timezone-aware comparison
        if last_date.tzinfo is None and now.tzinfo is not None:
            last_date = last_date.replace(tzinfo=timezone.utc)
            log.info(f"Made last_date timezone-aware: {last_date}")

        if last_date >= now:
            # Already up to date
            log.info(f"{asset.symbol} already up to date (last_date >= now)")
            return []

        log.info(f"Building time blocks from {last_date} to {now}")
        time_blocks = get_time_blocks(last_date, now, max_block_days)
        log.info(f"Created {len(time_blocks)} time blocks for {asset.symbol}")

        return [
            {
                "contract": contract,
                "symbol": asset.symbol,
                "from": block[0],
                "to": block[1],
            }
            for block in time_blocks
        ]

    def _build_future_update_items(
        self,
        asset: Asset,
        timeframe: TimeFrame,
        now: datetime,
        max_block_days: int,
    ) -> List[Dict[str, Any]]:
        """Build update items for futures."""
        items = []

        for cd in asset.contract_details:
            contract = cd.contract
            last_trade = self._parse_expiry_date(contract.last_trade_date)

            if last_trade is None:
                continue

            symbol = self._get_future_symbol(contract)
            last_date = self._repository.get_last_date(symbol, timeframe.value)

            # Determine the target end date
            # For expired contracts: update up to expiration
            # For active contracts: update up to now
            is_expired = last_trade < now
            target_end = last_trade if is_expired else now

            if last_date is None:
                # No data - start from beginning
                if is_expired:
                    # For expired contracts with no data, start 2 years before expiry
                    start = last_trade - timedelta(days=730)
                else:
                    start = now - timedelta(days=max_block_days)
            elif last_date >= target_end:
                continue  # Up to date (or complete for expired)
            else:
                start = last_date

            time_blocks = get_time_blocks(start, target_end, max_block_days)

            for block in time_blocks:
                items.append({
                    "contract": contract,
                    "symbol": symbol,
                    "from": block[0],
                    "to": block[1],
                })

        return items

    def _start_download_task(
        self,
        items: List[Dict[str, Any]],
        timeframe: str,
        progress: DownloadProgress,
        callback: Optional[Callable[[float], None]],
    ) -> None:
        """Start background download task."""
        self._running = True
        total = len(items)
        completed = [0]  # Use list for closure

        def download_thread():
            import time

            try:
                # Wait for broker connection before starting downloads
                if not self._wait_for_connection():
                    progress.error.emit("Broker not connected")
                    return

                # Small delay to ensure connection is fully stable
                time.sleep(0.5)

                log.info(f"Starting download of {total} items...")

                for item in items:
                    if not self._running:
                        break

                    # Check connection before each request
                    if not self._broker.is_connected():
                        log.error("Lost connection during download")
                        progress.error.emit("Lost connection to broker")
                        return

                    self._download_one(
                        item["contract"],
                        item["symbol"],
                        item["from"],
                        item["to"],
                        timeframe,
                    )

                    completed[0] += 1
                    pct = (completed[0] / total) * 100

                    progress.progress_changed.emit(pct)
                    if callback:
                        callback(pct)

                progress.completed.emit()

            except Exception as e:
                log.error(f"Download error: {e}")
                progress.error.emit(str(e))

        self._current_task = threading.Thread(
            target=download_thread, daemon=True
        )
        self._current_task.start()

    def _download_one(
        self,
        contract: Contract,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str,
    ) -> None:
        """Download one time block."""
        duration_days = (end - start).days

        log.info(
            f"Downloading {symbol}: {start.strftime('%Y%m%d')} - "
            f"{end.strftime('%Y%m%d')} ({duration_days} days)"
        )

        # Debug to file
        with open("/tmp/download_debug.txt", "a") as f:
            f.write(f"Download: {symbol} {start.strftime('%Y%m%d')} - {end.strftime('%Y%m%d')} ({duration_days} days)\n")

        # Use event to wait for callback
        done_event = threading.Event()
        bars_result: List[BarData] = []

        def on_bars(bars: List[BarData]):
            nonlocal bars_result
            with open("/tmp/download_debug.txt", "a") as f:
                f.write(f"  Callback received: bars={type(bars)}, len={len(bars) if bars else 'None'}\n")
            if bars:
                bars_result = bars
            done_event.set()

        self._broker.get_historical_data(
            contract=contract,
            end_datetime=end,
            duration=f"{duration_days} D",
            bar_size=timeframe,
            price_type="TRADES",
            callback=on_bars,
        )

        # Wait for response (with timeout)
        result = done_event.wait(timeout=self.DOWNLOAD_TIMEOUT)
        with open("/tmp/download_debug.txt", "a") as f:
            f.write(f"  Wait result: {result}, bars_count={len(bars_result)}\n")

        if bars_result:
            self._repository.append(symbol, timeframe, bars_result)
            log.info(f"Saved {len(bars_result)} bars for {symbol}")
            with open("/tmp/download_debug.txt", "a") as f:
                f.write(f"  Saved {len(bars_result)} bars\n")
        else:
            log.warning(f"No data received for {symbol}")
            with open("/tmp/download_debug.txt", "a") as f:
                f.write(f"  No data received\n")

    def _get_future_symbol(self, contract: Contract) -> str:
        """Get storage symbol for a future contract."""
        return f"{contract.local_symbol}-{contract.last_trade_date}"

    def _parse_expiry_date(self, date_str: str) -> Optional[datetime]:
        """Parse expiry date string."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None
