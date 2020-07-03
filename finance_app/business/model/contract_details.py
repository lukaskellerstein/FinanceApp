from ibapi.contract import ContractDetails
from db.model.base import DBObject
from business.model.contracts import (
    IBContract,
    IBStockContract,
)

from typing import Dict, Any
from business.helpers import dict_to_obj


class IBContractDetails(ContractDetails, DBObject):
    def __init__(self, **kwargs: Any):
        ContractDetails.__init__(self)
        DBObject.__init__(self, self.__module__, type(self).__name__)

        self.contract: IBContract = self.contract

        # dynamically set attributes
        for (k, v) in kwargs.items():
            setattr(self, k, v)
