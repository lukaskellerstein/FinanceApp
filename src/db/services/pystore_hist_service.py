import logging
import threading
from datetime import datetime
from typing import Any, List, Tuple
from src.business.model.timeframe import TimeFrame
import pandas as pd
import pystore
import time

# create logger
log = logging.getLogger("CellarLogger")


class PyStoreHistService(object):
    def __init__(self):
        self.lock = threading.Lock()
        pystore.set_path("./src/db/pystore")
        self.store = pystore.store("cellarstone_db")

    def __getNewDf(
        self, data: List[Tuple[datetime, float, float, float, float, float]]
    ) -> pd.DataFrame:
        my_df = pd.DataFrame(
            data,
            columns=["Datetime", "Open", "High", "Low", "Close", "Volume"],
        )
        # Convert to datetime with UTC timezone to match existing PyStore data format
        # Existing data is stored as datetime64[us, UTC], so new data must match
        my_df["Datetime"] = pd.to_datetime(my_df["Datetime"], utc=True)
        my_df.set_index(["Datetime"], inplace=True)
        return my_df

    def add(
        self,
        symbol: str,
        timeframe: TimeFrame,
        bars: List[Tuple[datetime, float, float, float, float, float]],
    ):
        if len(bars) > 0:
            self.lock.acquire()
            try:
                # log.info(bars)
                my_df = self.__getNewDf(bars)
                # log.info(my_df)

                t = timeframe.value.strip()

                collection = self.store.collection(t)

                # Clean up any leftover temporary items from failed appends
                temp_item_name = f"__{symbol}"
                if temp_item_name in collection.list_items():
                    log.warning(f"Cleaning up leftover temp item: {temp_item_name}")
                    collection.delete_item(temp_item_name)

                if symbol in collection.list_items():
                    item = collection.item(symbol)
                    collection.append(
                        symbol, my_df, npartitions=item.data.npartitions
                    )
                else:
                    collection.write(
                        symbol,
                        my_df,
                        metadata={"source": "InteractiveBrokers"},
                    )
            finally:
                self.lock.release()

    def getAll(self, symbol: str, timeframe: TimeFrame) -> pd.DataFrame:
        log.info(symbol)
        start = time.time()

        t = timeframe.value.strip()

        df = None
        try:
            collection = self.store.collection(t)

            if symbol in collection.list_items():
                item = collection.item(symbol)
                # data = item.data  # <-- Dask dataframe (see dask.pydata.org)
                # log.info(item)
                # log.info(data)
                # metadata = item.metadata
                # log.info(metadata)
                df = item.to_pandas()
        except FileNotFoundError as e:
            log.warning(f"Historical data directory not found for timeframe {t}: {e}")
        except Exception as e:
            log.error(f"Error loading historical data for {symbol}: {e}")

        end = time.time()
        log.info(f"takes {end - start} sec.")
        return df

    def removeAll(self, symbol, timeframe: TimeFrame):
        t = timeframe.value.strip()
        try:
            collection = self.store.collection(t)
            if symbol in collection.list_items():
                collection.delete_item(symbol)
                log.info(f"Removed historical data for {symbol}")
            else:
                log.info(f"No existing data to remove for {symbol}")
        except Exception as e:
            log.warning(f"Error removing data for {symbol}: {e}")
