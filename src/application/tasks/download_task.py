"""
Background download task for historical data.

Manages sequential downloading of multiple time blocks.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.interfaces.broker import IBrokerClient
from src.core.interfaces.repositories import IHistoricalDataRepository
from src.domain.entities.contract import Contract, FutureContract
from src.domain.entities.timeframe import TimeFrame
from src.domain.value_objects.bar_data import BarData

log = logging.getLogger("CellarLogger")


class DownloadProgress(QObject):
    """Signal emitter for download progress."""

    progress = pyqtSignal(float)  # 0-100
    item_completed = pyqtSignal(str)  # symbol
    all_completed = pyqtSignal()
    error = pyqtSignal(str)


class DownloadTask(threading.Thread):
    """
    Background task for downloading historical data.

    Downloads multiple time blocks sequentially, respecting IB rate limits.

    Example:
        task = DownloadTask(
            broker_client=ib_client,
            repository=pystore_repo,
            items=[
                {"contract": contract, "symbol": "AAPL", "from": dt1, "to": dt2},
                ...
            ],
            timeframe="1 day",
        )
        task.progress.progress.connect(update_ui)
        task.start()
    """

    # Maximum concurrent requests (IB limit)
    MAX_CONCURRENT = 1

    # Delay between requests (seconds)
    REQUEST_DELAY = 0.5

    # Request timeout (seconds)
    REQUEST_TIMEOUT = 60

    def __init__(
        self,
        broker_client: IBrokerClient,
        repository: IHistoricalDataRepository,
        items: List[Dict[str, Any]],
        timeframe: str,
        progress_callback: Optional[Callable[[float], None]] = None,
    ):
        """
        Initialize task.

        Args:
            broker_client: Broker client for data requests
            repository: Repository for storing data
            items: List of download items with contract, symbol, from, to
            timeframe: Timeframe string
            progress_callback: Optional callback for progress updates
        """
        super().__init__(daemon=True)

        self._broker = broker_client
        self._repository = repository
        self._items = items
        self._timeframe = timeframe
        self._progress_callback = progress_callback

        self._running = True
        self._completed = 0
        self._total = len(items)

        self.progress = DownloadProgress()

        log.info(f"DownloadTask initialized with {self._total} items")

    def run(self):
        """Execute the download task."""
        log.info("DownloadTask starting")
        start_time = time.time()

        try:
            for item in self._items:
                if not self._running:
                    log.info("DownloadTask cancelled")
                    break

                self._download_item(item)
                self._completed += 1

                # Report progress
                pct = (self._completed / self._total) * 100
                self.progress.progress.emit(pct)
                self.progress.item_completed.emit(item.get("symbol", ""))

                if self._progress_callback:
                    self._progress_callback(pct)

                # Rate limiting delay
                time.sleep(self.REQUEST_DELAY)

            self.progress.all_completed.emit()

        except Exception as e:
            log.error(f"DownloadTask error: {e}")
            self.progress.error.emit(str(e))

        elapsed = time.time() - start_time
        log.info(f"DownloadTask completed in {elapsed:.1f}s")

    def _download_item(self, item: Dict[str, Any]) -> None:
        """Download a single item."""
        contract: Contract = item["contract"]
        symbol: str = item.get("symbol", contract.symbol)
        start_dt: datetime = item["from"]
        end_dt: datetime = item["to"]

        duration_days = (end_dt - start_dt).days

        log.info(
            f"Downloading {symbol}: "
            f"{start_dt.strftime('%Y%m%d')} - {end_dt.strftime('%Y%m%d')} "
            f"({duration_days} days)"
        )

        # Event for synchronization
        done = threading.Event()
        result_bars: List[BarData] = []
        error_msg: Optional[str] = None

        def on_data(bars):
            nonlocal result_bars
            if bars is None:
                # Error occurred
                pass
            elif isinstance(bars, list):
                result_bars = bars
            done.set()

        # Request historical data
        self._broker.get_historical_data(
            contract=contract,
            end_datetime=end_dt,
            duration=f"{duration_days} D",
            bar_size=self._timeframe,
            price_type="TRADES",
            callback=on_data,
        )

        # Wait for response
        if not done.wait(timeout=self.REQUEST_TIMEOUT):
            log.warning(f"Timeout downloading {symbol}")
            return

        # Store data
        if result_bars:
            # Determine storage symbol (futures include expiry)
            storage_symbol = symbol
            if isinstance(contract, FutureContract):
                storage_symbol = (
                    f"{contract.local_symbol}-{contract.last_trade_date}"
                )

            self._repository.append(
                storage_symbol, self._timeframe, result_bars
            )
            log.info(f"Saved {len(result_bars)} bars for {storage_symbol}")
        else:
            log.warning(f"No data for {symbol}")

    def terminate(self) -> None:
        """Stop the task."""
        log.info("Terminating DownloadTask")
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if task is still running."""
        return self._running and self.is_alive()

    @property
    def completed_count(self) -> int:
        """Get number of completed items."""
        return self._completed

    @property
    def total_count(self) -> int:
        """Get total number of items."""
        return self._total

    @property
    def progress_percent(self) -> float:
        """Get current progress percentage."""
        if self._total == 0:
            return 100.0
        return (self._completed / self._total) * 100
