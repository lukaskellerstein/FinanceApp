from PyQt6.QtCore import QAbstractTableModel
from typing import List
from finance_app.business.model.contract_details import IBContractDetails
from finance_app.ui.components.contract_details_table.stock_table_model import (
    StockContractDetailsTableModel,
)
from finance_app.ui.components.contract_details_table.future_table_model import (
    FutureContractDetailsTableModel,
)


class ContractDetailsTableModelFactory(object):
    @staticmethod
    def create(
        contractType: str, data: List[IBContractDetails]
    ) -> QAbstractTableModel:
        if contractType == "stock":
            return StockContractDetailsTableModel(data)
        elif contractType == "future":
            return FutureContractDetailsTableModel(data)
        else:
            return None
