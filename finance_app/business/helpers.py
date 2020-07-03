

from datetime import datetime, timedelta
import importlib
from typing import Any, List, Tuple

import pandas as pd

from db.model.base import DBObject
from ibapi.contract import Contract, ContractDetails

types = (ContractDetails, Contract, DBObject)

def obj_to_dict(obj: Any, omitKeys: List[str] = []) -> Any:
    if isinstance(obj, types):
        # print(vars(obj))
        return obj_to_dict(vars(obj), omitKeys)
    elif type(obj) is dict:
        res = {}
        for k, v in obj.items():
            if k not in omitKeys:
                res[k] = obj_to_dict(v, omitKeys)
        return res
    elif type(obj) is list:
        return [obj_to_dict(item, omitKeys) for item in obj]
    else:
        return obj


def dict_to_obj(data: Any) -> Any:
    if type(data) is dict:
        instance = None
        if "_className" in data and "_moduleName" in data:
            modPath = data["_moduleName"]
            clN = data["_className"]
            module = importlib.import_module(modPath)
            class_ = getattr(module, clN)
            instance = class_()

        for k, v in data.items():
            instance.__setattr__(k, dict_to_obj(v))
        
        return instance
    elif type(data) is list:
        return [dict_to_obj(item) for item in data]
    else:
        return data



def getTimeBlocks(start: datetime, end: datetime, days: int = 7) -> List[Tuple[datetime, datetime]]:
    result = []

    # date_format = "%m/%d/%Y"
    # d1 = datetime.strptime("2/6/2017", date_format).date()
    # d2 = datetime.strptime("3/5/2017", date_format).date()
    d = start
    step = timedelta(days=days)

    while d <= end:
        tempStart = d
        d += step
        # print(f"from: {tempStart.strftime('%Y%m%d')}, to: {d.strftime('%Y%m%d')}")
        result.append((tempStart, d))

    return result

