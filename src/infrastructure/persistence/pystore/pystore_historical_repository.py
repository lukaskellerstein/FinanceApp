"""
PyStore-based historical data repository implementation.

Implements IHistoricalDataRepository using PyStore for efficient
columnar storage of OHLCV data.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

import pandas as pd
import pystore

from src.core.interfaces.repositories import IHistoricalDataRepository
from src.domain.entities.timeframe import TimeFrame
from src.domain.value_objects.bar_data import BarData

log = logging.getLogger("CellarLogger")


class PyStoreHistoricalRepository(IHistoricalDataRepository):
    """
    PyStore-based historical data repository.

    Uses PyStore for efficient storage and retrieval of OHLCV
    time series data. Data is organized by timeframe (collection)
    and symbol (item).

    Structure:
        store/
            1 day/
                AAPL/
                IBM/
            1 hour/
                AAPL/

    Example:
        repo = PyStoreHistoricalRepository("./data/pystore", "my_store")
        repo.save("AAPL", "1 day", bars)
        df = repo.get("AAPL", "1 day")
    """

    def __init__(self, base_path: str, store_name: str = "cellarstone_db"):
        """
        Initialize repository.

        Args:
            base_path: Base path for PyStore data
            store_name: Name of the PyStore store
        """
        self.base_path = base_path
        self.store_name = store_name
        self.lock = threading.Lock()

        pystore.set_path(base_path)
        self.store = pystore.store(store_name)

    def _normalize_timeframe(self, timeframe: str) -> str:
        """
        Normalize timeframe string.

        Args:
            timeframe: Timeframe string (e.g., "1 day", "1 hour")

        Returns:
            Normalized timeframe string
        """
        return timeframe.strip()

    def _bars_to_dataframe(self, bars: List[BarData]) -> pd.DataFrame:
        """
        Convert list of BarData to DataFrame.

        Args:
            bars: List of BarData objects

        Returns:
            DataFrame with OHLCV data
        """
        data = [
            (bar.datetime, bar.open, bar.high, bar.low, bar.close, bar.volume)
            for bar in bars
        ]

        df = pd.DataFrame(
            data,
            columns=["Datetime", "Open", "High", "Low", "Close", "Volume"],
        )

        # Convert to datetime with UTC timezone to match existing format
        df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
        df.set_index(["Datetime"], inplace=True)

        return df

    def _tuples_to_dataframe(
        self,
        tuples: List[Tuple[datetime, float, float, float, float, int]],
    ) -> pd.DataFrame:
        """
        Convert list of tuples to DataFrame.

        Args:
            tuples: List of (datetime, open, high, low, close, volume) tuples

        Returns:
            DataFrame with OHLCV data
        """
        df = pd.DataFrame(
            tuples,
            columns=["Datetime", "Open", "High", "Low", "Close", "Volume"],
        )

        df["Datetime"] = pd.to_datetime(df["Datetime"], utc=True)
        df.set_index(["Datetime"], inplace=True)

        return df

    def _cleanup_temp_items(self, collection: Any, symbol: str) -> None:
        """
        Clean up temporary items from failed appends.

        Args:
            collection: PyStore collection
            symbol: Symbol name
        """
        temp_item = f"__{symbol}"
        if temp_item in collection.list_items():
            log.warning(f"Cleaning up leftover temp item: {temp_item}")
            try:
                collection.delete_item(temp_item)
            except Exception as e:
                log.warning(f"Failed to clean temp item: {e}")

    # ----------------------------------------------------------------
    # IHistoricalDataRepository Implementation
    # ----------------------------------------------------------------

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get historical data for a symbol.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe (e.g., "1 day")

        Returns:
            DataFrame with OHLCV data or None
        """
        tf = self._normalize_timeframe(timeframe)
        start = time.time()

        try:
            collection = self.store.collection(tf)

            if symbol in collection.list_items():
                item = collection.item(symbol)
                df = item.to_pandas()

                elapsed = time.time() - start
                log.info(f"Loaded {symbol}/{tf} in {elapsed:.3f}s")
                return df

            return None

        except FileNotFoundError as e:
            log.warning(f"Data directory not found for {tf}: {e}")
            return None
        except Exception as e:
            log.error(f"Error loading {symbol}/{tf}: {e}")
            return None

    def save(self, symbol: str, timeframe: str, data: Any) -> None:
        """
        Save historical data (overwrite).

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data: Data to save (DataFrame, List[BarData], or List[Tuple])
        """
        tf = self._normalize_timeframe(timeframe)

        # Convert data to DataFrame
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], BarData):
                df = self._bars_to_dataframe(data)
            elif isinstance(data[0], tuple):
                df = self._tuples_to_dataframe(data)
            else:
                raise ValueError(f"Unsupported data type: {type(data[0])}")
        else:
            log.warning(f"Empty data for {symbol}/{tf}, skipping save")
            return

        with self.lock:
            try:
                collection = self.store.collection(tf)
                self._cleanup_temp_items(collection, symbol)

                # Delete existing item if present
                if symbol in collection.list_items():
                    collection.delete_item(symbol)

                # Write new data
                collection.write(
                    symbol,
                    df,
                    metadata={"source": "InteractiveBrokers"},
                )

                log.info(f"Saved {len(df)} bars for {symbol}/{tf}")

            except Exception as e:
                log.error(f"Error saving {symbol}/{tf}: {e}")
                raise

    def append(self, symbol: str, timeframe: str, data: Any) -> None:
        """
        Append historical data to existing data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
            data: Data to append
        """
        tf = self._normalize_timeframe(timeframe)

        if not data or (isinstance(data, list) and len(data) == 0):
            log.warning(f"Empty data for append {symbol}/{tf}")
            return

        # Convert data to DataFrame
        if isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, list):
            if isinstance(data[0], BarData):
                df = self._bars_to_dataframe(data)
            elif isinstance(data[0], tuple):
                df = self._tuples_to_dataframe(data)
            else:
                raise ValueError(f"Unsupported data type: {type(data[0])}")
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        with self.lock:
            try:
                collection = self.store.collection(tf)
                self._cleanup_temp_items(collection, symbol)

                if symbol in collection.list_items():
                    item = collection.item(symbol)
                    collection.append(
                        symbol,
                        df,
                        npartitions=item.data.npartitions,
                    )
                    log.info(f"Appended {len(df)} bars to {symbol}/{tf}")
                else:
                    collection.write(
                        symbol,
                        df,
                        metadata={"source": "InteractiveBrokers"},
                    )
                    log.info(f"Created {symbol}/{tf} with {len(df)} bars")

            except Exception as e:
                log.error(f"Error appending {symbol}/{tf}: {e}")
                raise

    def delete(self, symbol: str, timeframe: str) -> None:
        """
        Delete historical data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe
        """
        tf = self._normalize_timeframe(timeframe)

        try:
            collection = self.store.collection(tf)

            if symbol in collection.list_items():
                collection.delete_item(symbol)
                log.info(f"Deleted {symbol}/{tf}")
            else:
                log.info(f"No data to delete for {symbol}/{tf}")

        except Exception as e:
            log.warning(f"Error deleting {symbol}/{tf}: {e}")

    def get_last_date(self, symbol: str, timeframe: str) -> Optional[datetime]:
        """
        Get the last date of stored data.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            Last datetime or None if no data
        """
        df = self.get(symbol, timeframe)

        if df is not None and len(df) > 0:
            last_index = df.index[-1]
            # Convert pandas Timestamp to datetime
            if hasattr(last_index, "to_pydatetime"):
                return last_index.to_pydatetime()
            return last_index

        return None

    def exists(self, symbol: str, timeframe: str) -> bool:
        """
        Check if data exists for symbol/timeframe.

        Args:
            symbol: Asset symbol
            timeframe: Timeframe

        Returns:
            True if data exists
        """
        tf = self._normalize_timeframe(timeframe)

        try:
            collection = self.store.collection(tf)
            return symbol in collection.list_items()
        except FileNotFoundError:
            return False
        except Exception as e:
            log.warning(f"Error checking existence of {symbol}/{tf}: {e}")
            return False

    def get_symbols(self, timeframe: str) -> List[str]:
        """
        Get all symbols with data for a timeframe.

        Args:
            timeframe: Timeframe

        Returns:
            List of symbols
        """
        tf = self._normalize_timeframe(timeframe)

        try:
            collection = self.store.collection(tf)
            return list(collection.list_items())
        except FileNotFoundError:
            return []
        except Exception as e:
            log.warning(f"Error listing symbols for {tf}: {e}")
            return []

    def get_symbols_matching(self, pattern: str, timeframe: str) -> List[str]:
        """
        Get all symbols matching a pattern for a timeframe.

        For futures, this matches the base symbol and all contracts.
        Supports both hierarchical format (ES/ESH5-20250321) and legacy flat format.

        Args:
            pattern: Pattern to match (base symbol)
            timeframe: Timeframe

        Returns:
            List of matching symbols
        """
        tf = self._normalize_timeframe(timeframe)

        try:
            collection = self.store.collection(tf)
            all_symbols = list(collection.list_items())

            matching = []
            for symbol in all_symbols:
                # Match exact symbol
                if symbol == pattern:
                    matching.append(symbol)
                # Match hierarchical futures: pattern/subcontract (e.g., ES/ESH5-20250321)
                elif symbol.startswith(f"{pattern}/"):
                    matching.append(symbol)
                # Legacy flat format for backwards compatibility
                elif symbol.startswith(pattern) and len(symbol) > len(pattern):
                    suffix = symbol[len(pattern):]
                    if suffix[0].isalpha() and (
                        len(suffix) > 1 and (suffix[1].isdigit() or suffix[1] == "-")
                    ):
                        matching.append(symbol)

            return matching
        except FileNotFoundError:
            return []
        except Exception as e:
            log.warning(f"Error finding symbols matching {pattern}/{tf}: {e}")
            return []

    def delete_matching(self, pattern: str, timeframe: str) -> int:
        """
        Delete all historical data matching a pattern.

        Args:
            pattern: Pattern to match (e.g., "CL" to delete all CL contracts)
            timeframe: Timeframe

        Returns:
            Number of items deleted
        """
        tf = self._normalize_timeframe(timeframe)
        matching = self.get_symbols_matching(pattern, tf)

        deleted_count = 0
        with self.lock:
            try:
                collection = self.store.collection(tf)

                for symbol in matching:
                    try:
                        if symbol in collection.list_items():
                            collection.delete_item(symbol)
                            deleted_count += 1
                            log.info(f"Deleted {symbol}/{tf}")
                    except Exception as e:
                        log.warning(f"Error deleting {symbol}/{tf}: {e}")

                log.info(f"Deleted {deleted_count} items matching {pattern}/{tf}")
                return deleted_count

            except Exception as e:
                log.error(f"Error deleting matching {pattern}/{tf}: {e}")
                return deleted_count
