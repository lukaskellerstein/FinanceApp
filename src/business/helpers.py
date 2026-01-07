from datetime import datetime, timedelta
import importlib
from typing import Any, List, Tuple

import pandas as pd

from src.db.model.base import DBObject
from ibapi.contract import Contract, ContractDetails


def getTimeBlocks(
    start: datetime, end: datetime, blockInDays: int = 7
) -> List[Tuple[datetime, datetime]]:

    diff = (end - start).days

    if diff < blockInDays:
        return [(start, end)]
    else:

        # date_format = "%m/%d/%Y"
        # d1 = datetime.strptime("2/6/2017", date_format).date()
        # d2 = datetime.strptime("3/5/2017", date_format).date()
        result = []
        d = start
        step = timedelta(days=blockInDays)

        while d < end:
            tempStart = d
            d += step
            # Ensure the block end date doesn't exceed the requested end date
            blockEnd = min(d, end)
            # print(f"from: {tempStart.strftime('%Y%m%d')}, to: {blockEnd.strftime('%Y%m%d')}")
            result.append((tempStart, blockEnd))

        return result

