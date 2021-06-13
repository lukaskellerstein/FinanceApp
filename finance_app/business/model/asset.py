from __future__ import (
    annotations,
)  # allow return same type as class ..... -> State

from business.model.contract_details import IBContractDetails
from typing import List, Dict, Any
from db.model.base import DBObject
from enum import Enum


class AssetType(Enum):
    NONE = "none"
    STOCK = "stock"
    FUTURE = "future"

    @staticmethod
    def from_str(value: str) -> AssetType:
        if value.lower() == AssetType.STOCK.value:
            return AssetType.STOCK
        elif value.lower() == AssetType.FUTURE.value:
            return AssetType.FUTURE
        else:
            return AssetType.NONE


class Asset(DBObject):
    def __init__(self):
        DBObject.__init__(self, self.__module__, type(self).__name__)

        self.symbol: str = ""
        self.shortDescription: str = ""
        self.type: str = ""
        self.contractDetails: List[IBContractDetails] = []

